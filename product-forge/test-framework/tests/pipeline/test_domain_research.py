"""Tests for Domain Research Engine"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestDomainResearchEngine:
    def test_create_engine(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        assert engine is not None
        assert len(engine.domain_data) > 0

    def test_get_all_domains(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        domains = engine.get_all_domains()
        assert "finance" in domains
        assert "healthcare" in domains
        assert "ecommerce" in domains
        assert "ai_ml" in domains
        assert "productivity" in domains

    def test_get_domain_trends_finance(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        trends = engine.get_domain_trends("finance")
        assert len(trends) > 0
        assert any("Embedded" in t.name for t in trends)

    def test_get_domain_trends_unknown(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        trends = engine.get_domain_trends("unknown_domain")
        assert len(trends) == 0

    def test_get_domain_best_practices(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        practices = engine.get_domain_best_practices("finance")
        assert len(practices) > 0
        assert any("PCI" in p.title for p in practices)

    def test_search_trends_by_keyword(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        results = engine.search_trends("AI")
        assert len(results) > 0

    def test_search_trends_no_results(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        results = engine.search_trends("xyznonexistent")
        assert len(results) == 0

    def test_generate_research_report(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        report = engine.generate_research_report("finance")
        assert "Finance" in report
        assert "Research" in report
        assert "Trends" in report
        assert "Best Practices" in report
        assert "Recommendations" in report

    def test_generate_research_report_unknown_domain(self):
        from core.domain_research import DomainResearchEngine
        engine = DomainResearchEngine()
        report = engine.generate_research_report("unknown")
        assert "Unknown" in report or "unknown" in report.lower()
        assert "Research" in report
