"""
Cross-Agent Review Mechanism
Agent A's work is reviewed by Agent B or C for different perspectives.
Feedback is tracked to closure.

Industry Standard: Peer review with different reviewers providing
different angles (security, performance, code quality, UX, etc.)

Provides:
- Review assignment (different LLM reviews different agent's work)
- Feedback tracking with status (open, addressed, dismissed)
- Review history and metrics
- Cross-perspective reviews (security reviews code, UX reviews API, etc.)
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class ReviewRequest:
    """Request for cross-agent review"""
    id: str
    target_agent: str  # Agent being reviewed
    reviewer_agent: str  # Agent doing the review
    stage: int
    artifact_path: str
    artifact_type: str  # code, design, architecture, test, docs
    status: str = "pending"  # pending, in_review, completed, dismissed
    requested_at: Optional[str] = None
    completed_at: Optional[str] = None
    summary: Optional[str] = None
    verdict: Optional[str] = None  # approved, changes_required, rejected
    feedback_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ReviewFeedback:
    """Individual feedback item from a review"""
    id: str
    review_id: str
    severity: str  # critical, major, minor, suggestion
    category: str  # security, performance, quality, ux, architecture, compliance
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: str = ""
    suggestion: Optional[str] = None
    status: str = "open"  # open, addressed, dismissed, deferred
    addressed_by: Optional[str] = None
    addressed_at: Optional[str] = None
    agent_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewFeedback":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Review matrix: which agents review which types of work
REVIEW_MATRIX = {
    # Agent being reviewed -> list of reviewers
    "ideation": ["design", "architect", "review"],
    "design": ["architect", "review", "security"],
    "architect": ["review", "security", "implement"],
    "implement": ["code-review", "security", "validate"],
    "code-review": ["security", "validate"],
    "validate": ["review", "security"],
    "fix": ["code-review", "validate"],
    "security": ["review", "code-review"],
    "document": ["review", "design"],
    "package": ["devops", "security"],
    "devops": ["security", "review"],
}

# Review focus areas per reviewer
REVIEW_FOCUS = {
    "security": ["vulnerability", "injection", "auth", "encryption", "compliance"],
    "performance": ["latency", "memory", "cpu", "scalability", "caching"],
    "quality": ["code-review", "testing", "documentation", "maintainability"],
    "architecture": ["design-pattern", "coupling", "cohesion", "modularity"],
    "ux": ["usability", "accessibility", "responsive", "consistency"],
    "compliance": ["regulatory", "audit", "policy", "licensing"],
}


class CrossReviewManager:
    """
    Manages cross-agent reviews and feedback tracking.

    Workflow:
    1. Agent completes work -> ReviewRequest created
    2. Reviewer agent analyzes -> ReviewFeedback items generated
    3. Original agent addresses feedback -> status updated
    4. Reviewer verifies -> feedback closed
    5. Metrics tracked for quality improvement
    """

    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.reviews_dir = self.project_dir / "reviews"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

        self.review_file = self.reviews_dir / "cross-reviews.json"
        self._load_or_create()

    def _load_or_create(self):
        if self.review_file.exists():
            with open(self.review_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._create_empty()

    def _create_empty(self) -> Dict[str, Any]:
        return {
            "$schema": "cross-review-v1",
            "version": "1.0.0",
            "review_requests": [],
            "feedback": [],
            "summary": {
                "total_reviews": 0,
                "completed_reviews": 0,
                "total_feedback": 0,
                "addressed_feedback": 0,
                "avg_feedback_per_review": 0,
            },
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "cross_review_manager",
            },
        }

    # ==================== REVIEW REQUESTS ====================

    def request_review(
        self,
        target_agent: str,
        reviewer_agent: str,
        stage: int,
        artifact_path: str,
        artifact_type: str = "code",
    ) -> ReviewRequest:
        """Request a cross-agent review"""
        review_id = f"review-{target_agent}-{reviewer_agent}-{stage}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        request = ReviewRequest(
            id=review_id,
            target_agent=target_agent,
            reviewer_agent=reviewer_agent,
            stage=stage,
            artifact_path=artifact_path,
            artifact_type=artifact_type,
            status="pending",
            requested_at=datetime.now(timezone.utc).isoformat(),
        )

        self.data["review_requests"].append(request.to_dict())
        self._update_summary()
        self._save()
        return request

    def request_auto_reviews(self, target_agent: str, stage: int, artifact_path: str) -> List[ReviewRequest]:
        """Automatically request reviews from appropriate agents"""
        reviewers = REVIEW_MATRIX.get(target_agent, ["review"])
        requests = []

        for reviewer in reviewers:
            if reviewer != target_agent:  # Don't review yourself
                request = self.request_review(
                    target_agent=target_agent,
                    reviewer_agent=reviewer,
                    stage=stage,
                    artifact_path=artifact_path,
                    artifact_type=self._guess_artifact_type(artifact_path),
                )
                requests.append(request)

        return requests

    def update_review_status(self, review_id: str, status: str, summary: str = None, verdict: str = None):
        """Update review request status"""
        for review in self.data["review_requests"]:
            if review["id"] == review_id:
                review["status"] = status
                if summary:
                    review["summary"] = summary
                if verdict:
                    review["verdict"] = verdict
                if status in ("completed", "dismissed"):
                    review["completed_at"] = datetime.now(timezone.utc).isoformat()
                break
        self._update_summary()
        self._save()

    # ==================== FEEDBACK ====================

    def add_feedback(
        self,
        review_id: str,
        severity: str,
        category: str,
        description: str,
        file_path: str = None,
        line_number: int = None,
        suggestion: str = None,
    ) -> ReviewFeedback:
        """Add feedback to a review"""
        feedback_id = f"fb-{review_id}-{len(self.data['feedback']) + 1}"

        feedback = ReviewFeedback(
            id=feedback_id,
            review_id=review_id,
            severity=severity,
            category=category,
            file_path=file_path,
            line_number=line_number,
            description=description,
            suggestion=suggestion,
            status="open",
        )

        self.data["feedback"].append(feedback.to_dict())

        # Update feedback count on review
        for review in self.data["review_requests"]:
            if review["id"] == review_id:
                review["feedback_count"] = review.get("feedback_count", 0) + 1
                break

        self._update_summary()
        self._save()
        return feedback

    def address_feedback(self, feedback_id: str, addressed_by: str, response: str = None):
        """Mark feedback as addressed"""
        for fb in self.data["feedback"]:
            if fb["id"] == feedback_id:
                fb["status"] = "addressed"
                fb["addressed_by"] = addressed_by
                fb["addressed_at"] = datetime.now(timezone.utc).isoformat()
                if response:
                    fb["agent_response"] = response
                break
        self._update_summary()
        self._save()

    def dismiss_feedback(self, feedback_id: str, reason: str = None):
        """Dismiss feedback (not applicable or already handled)"""
        for fb in self.data["feedback"]:
            if fb["id"] == feedback_id:
                fb["status"] = "dismissed"
                if reason:
                    fb["agent_response"] = f"Dismissed: {reason}"
                break
        self._update_summary()
        self._save()

    def get_open_feedback(self, review_id: str = None) -> List[ReviewFeedback]:
        """Get open feedback items"""
        items = []
        for fb in self.data["feedback"]:
            if fb.get("status") == "open":
                if review_id and fb.get("review_id") != review_id:
                    continue
                items.append(ReviewFeedback.from_dict(fb))
        return items

    def get_feedback_by_category(self, category: str) -> List[ReviewFeedback]:
        """Get feedback filtered by category"""
        return [
            ReviewFeedback.from_dict(fb)
            for fb in self.data["feedback"]
            if fb.get("category") == category
        ]

    # ==================== METRICS ====================

    def get_review_metrics(self) -> Dict[str, Any]:
        """Get review quality metrics"""
        reviews = self.data.get("review_requests", [])
        feedback = self.data.get("feedback", [])

        total_reviews = len(reviews)
        completed = sum(1 for r in reviews if r.get("status") == "completed")
        total_feedback = len(feedback)
        addressed = sum(1 for f in feedback if f.get("status") == "addressed")

        # Feedback by severity
        by_severity = {}
        for f in feedback:
            sev = f.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # Feedback by category
        by_category = {}
        for f in feedback:
            cat = f.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        # Reviewer metrics
        reviewer_stats = {}
        for r in reviews:
            reviewer = r.get("reviewer_agent", "unknown")
            if reviewer not in reviewer_stats:
                reviewer_stats[reviewer] = {"reviews": 0, "feedback_given": 0}
            reviewer_stats[reviewer]["reviews"] += 1
            reviewer_stats[reviewer]["feedback_given"] += r.get("feedback_count", 0)

        return {
            "total_reviews": total_reviews,
            "completed_reviews": completed,
            "completion_rate": completed / total_reviews if total_reviews > 0 else 0,
            "total_feedback": total_feedback,
            "addressed_feedback": addressed,
            "addressing_rate": addressed / total_feedback if total_feedback > 0 else 0,
            "avg_feedback_per_review": total_feedback / total_reviews if total_reviews > 0 else 0,
            "by_severity": by_severity,
            "by_category": by_category,
            "reviewer_stats": reviewer_stats,
        }

    def get_agent_quality_score(self, agent: str) -> Dict[str, Any]:
        """Get quality score for a specific agent based on reviews received"""
        reviews_received = [
            r for r in self.data.get("review_requests", [])
            if r.get("target_agent") == agent
        ]

        feedback_received = []
        for r in reviews_received:
            for f in self.data.get("feedback", []):
                if f.get("review_id") == r["id"]:
                    feedback_received.append(f)

        total = len(feedback_received)
        critical = sum(1 for f in feedback_received if f.get("severity") == "critical")
        major = sum(1 for f in feedback_received if f.get("severity") == "major")
        addressed = sum(1 for f in feedback_received if f.get("status") == "addressed")

        # Quality score: 100 - (critical*10 + major*5 + minor*1)
        score = max(0, 100 - (critical * 10 + major * 5 + (total - critical - major) * 1))

        return {
            "agent": agent,
            "reviews_received": len(reviews_received),
            "total_feedback": total,
            "critical_issues": critical,
            "major_issues": major,
            "addressed_rate": addressed / total if total > 0 else 0,
            "quality_score": score,
        }

    # ==================== HELPERS ====================

    def _guess_artifact_type(self, path: str) -> str:
        """Guess artifact type from file path"""
        if path.endswith((".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c")):
            return "code"
        elif path.endswith((".md", ".txt", ".rst")):
            return "docs"
        elif path.endswith((".yaml", ".yml", ".json", ".toml")):
            return "config"
        elif path.endswith((".html", ".css", ".scss")):
            return "ui"
        return "code"

    def _update_summary(self):
        """Update summary statistics"""
        reviews = self.data.get("review_requests", [])
        feedback = self.data.get("feedback", [])

        self.data["summary"] = {
            "total_reviews": len(reviews),
            "completed_reviews": sum(1 for r in reviews if r.get("status") == "completed"),
            "total_feedback": len(feedback),
            "addressed_feedback": sum(1 for f in feedback if f.get("status") == "addressed"),
            "avg_feedback_per_review": len(feedback) / len(reviews) if reviews else 0,
        }

    def _save(self):
        """Save review data to disk"""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.review_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
