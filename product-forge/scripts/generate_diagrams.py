#!/usr/bin/env python3
"""
Generate pipeline architecture diagrams using the diagrams library.
Usage: python generate_diagrams.py
"""

from diagrams import Diagram, Edge
from diagrams.generic import compute, storage, network
from diagrams.programming.flowchart import (
    Action, Decision, Display, InputOutput, StartEnd, Document
)


def generate_pipeline_flow():
    """Generate the main pipeline flow diagram."""
    with Diagram(
        "Multi-Agent Pipeline - E2E Flow",
        filename="docs/pipeline-flow",
        show=False,
        direction="LR",
        graph_attr={"fontsize": "20", "bgcolor": "white", "rankdir": "LR"},
    ):
        # User Layer
        user = InputOutput("User (IDE/CLI)")

        # Stage 0
        s0 = StartEnd("Stage 0\nIdeation\n(Orchestrator)")
        summary = Action("Summary &\nConfirmation")
        agent_meeting = Display("Agent Query\nMeeting")

        # Stages 1-3
        s1 = StartEnd("Stage 1\nDesign")
        s2 = StartEnd("Stage 2\nArchitect")
        s3 = StartEnd("Stage 3\nReview\n(APPROVED)")

        # Stages 4-7
        s4 = StartEnd("Stage 4\nImplement")
        s5 = StartEnd("Stage 5\nCode Review")
        s6 = StartEnd("Stage 6\nValidate")
        s7 = StartEnd("Stage 7\nFix Loop")

        # Artifacts
        plan = Document("product-plan.md")
        reqs = Document("requirements.md")
        design_doc = Document("design.md")
        arch_doc = Document("architecture.md")
        review_doc = Document("review.md")
        code = storage.Storage("src/")
        cr_doc = Document("code-review.md")
        issues = Document("issues.md")

        # Flow
        user >> Edge(label="New Idea") >> s0
        s0 >> summary >> agent_meeting
        agent_meeting >> plan
        plan >> s1
        s1 >> reqs >> s2
        s1 >> design_doc >> s2
        s2 >> arch_doc >> s3
        s3 >> Edge(label="APPROVED", color="green") >> s4
        s4 >> code >> s5
        s5 >> cr_doc >> s6
        s6 >> issues
        issues >> Edge(label="has issues", color="red") >> s7
        s7 >> Edge(label="fix", color="orange") >> code
        s7 >> Edge(label="re-validate", color="blue", style="dashed") >> s6


def generate_ideation_flow():
    """Generate the enhanced ideation flow diagram."""
    with Diagram(
        "Ideation Flow (Enhanced)",
        filename="docs/ideation-flow",
        show=False,
        direction="LR",
        graph_attr={"fontsize": "18", "bgcolor": "white"},
    ):
        idea = InputOutput("User Idea\n(Text or File)")
        read_file = Action("Read File\n(if file)")
        summarize = Action("Summarize:\nProblem\nUsers\nFeatures\nScope")
        confirm = Decision("User\nConfirms?")
        agent_meet = Display("Agent Meeting\n(All 7 agents)")
        optional = Action("Collect\nOptional Reqs")
        synthesize = Action("Synthesize\nproduct-plan.md")
        output = Document("product-plan.md\n(MUST-HAVE +\nOPTIONAL)")

        idea >> read_file >> summarize >> confirm
        confirm >> Edge(label="Changes", color="red") >> summarize
        confirm >> Edge(label="Confirmed", color="green") >> agent_meet
        agent_meet >> optional >> synthesize >> output


def generate_fix_loop():
    """Generate the fix loop diagram."""
    with Diagram(
        "Fix Loop",
        filename="docs/fix-loop",
        show=False,
        direction="LR",
        graph_attr={"fontsize": "18", "bgcolor": "white"},
    ):
        validate = StartEnd("Validate\nAgent")
        issues = Document("issues.md")
        fix = StartEnd("Fix\nAgent")
        code = storage.Storage("src/")
        done = StartEnd("Done")

        validate >> issues
        issues >> Edge(label="has issues", color="red") >> fix
        fix >> code >> validate
        issues >> Edge(label="empty", color="green") >> done


def generate_recovery():
    """Generate the recovery flow diagram."""
    with Diagram(
        "Recovery Flow",
        filename="docs/recovery-flow",
        show=False,
        direction="TB",
        graph_attr={"fontsize": "18", "bgcolor": "white"},
    ):
        fail = InputOutput("Agent\nFails")
        retry = Action("Retry")
        check = Decision("Retry\nSuccessful?")
        breaker_open = StartEnd("Circuit Breaker\nOPEN")
        cooldown = Action("Cooldown")
        half_open = Decision("Half-Open")
        probe = Action("Probe")
        probe_ok = Decision("Probe\nOK?")
        closed = StartEnd("Breaker\nCLOSED")
        dlq = storage.Storage("Dead Letter\nQueue")

        fail >> retry >> check
        check >> Edge(label="Yes", color="green") >> closed
        check >> Edge(label="No (5+)", color="red") >> breaker_open
        breaker_open >> cooldown >> half_open >> probe >> probe_ok
        probe_ok >> Edge(label="Yes", color="green") >> closed
        probe_ok >> Edge(label="No", color="red") >> dlq


def generate_artifact_flow():
    """Generate the artifact flow diagram."""
    with Diagram(
        "Artifact Flow",
        filename="docs/artifact-flow",
        show=False,
        direction="TB",
        graph_attr={"fontsize": "18", "bgcolor": "white"},
    ):
        plan = Document("product-plan.md")
        reqs = Document("requirements.md")
        design_doc = Document("design.md")
        arch_doc = Document("architecture.md")
        review_doc = Document("review.md")
        code = storage.Storage("src/")
        cr_doc = Document("code-review.md")
        issues = Document("issues.md")

        plan >> reqs
        plan >> design_doc
        reqs >> arch_doc
        design_doc >> arch_doc
        arch_doc >> review_doc
        review_doc >> Edge(label="APPROVED", color="green") >> code
        code >> cr_doc >> issues


if __name__ == "__main__":
    print("Generating pipeline diagrams...")
    generate_pipeline_flow()
    print("  Done: docs/pipeline-flow.png")
    generate_ideation_flow()
    print("  Done: docs/ideation-flow.png")
    generate_fix_loop()
    print("  Done: docs/fix-loop.png")
    generate_recovery()
    print("  Done: docs/recovery-flow.png")
    generate_artifact_flow()
    print("  Done: docs/artifact-flow.png")
    print("\nAll diagrams generated in docs/")
