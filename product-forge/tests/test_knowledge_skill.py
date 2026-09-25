"""
Test script to verify Knowledge Compiler and Skill Contracts functionality.
"""
import sys
import os
import tempfile
import shutil
from datetime import datetime

# Add current directory to path
sys.path.insert(0, '.')

def test_knowledge_compiler():
    """Test the KnowledgeCompiler module."""
    print("Testing KnowledgeCompiler...")
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    try:
        from core.knowledge_compiler import KnowledgeCompiler, Concept, Relationship, CompiledKnowledge
        
        # Initialize compiler with temp directory
        compiler = KnowledgeCompiler(knowledge_dir=temp_dir)
        
        # Test text with concepts
        test_text = """
        Python is a programming language.
        Machine learning is a subset of artificial intelligence.
        Neural networks are used in deep learning.
        Data preprocessing is essential for machine learning.
        Python supports multiple programming paradigms.
        """
        
        # Compile knowledge
        knowledge = compiler.compile_from_text(
            text=test_text,
            domain="ai_programming",
            source="test_document"
        )
        
        # Verify compilation
        assert knowledge.domain == "ai_programming"
        assert knowledge.source_count == 1
        assert len(knowledge.concepts) > 0
        print(f"  [OK] Extracted {len(knowledge.concepts)} concepts")
        
        # Verify concepts have required fields
        for concept in knowledge.concepts:
            assert concept.concept_id
            assert concept.name
            assert concept.definition
            assert concept.category in ["fact", "principle", "pattern", "rule"]
            assert 0 <= concept.confidence <= 1
            assert concept.source == "test_document"
        
        # Verify relationships
        print(f"  [OK] Extracted {len(knowledge.relationships)} relationships")
        for rel in knowledge.relationships:
            assert rel.relationship_id
            assert rel.source_concept
            assert rel.target_concept
            assert rel.relationship_type
        
        # Verify storage
        assert os.path.exists(os.path.join(compiler.compiled_dir, f"{knowledge.knowledge_id}.json"))
        print("  [OK] Knowledge stored to disk")
        
        # Test query
        results = compiler.query(domain="ai_programming")
        assert len(results) > 0
        print(f"  [OK] Query returned {len(results)} results")
        
        # Test concept name query
        results = compiler.query(concept_name="Python")
        assert len(results) > 0
        print(f"  [OK] Concept name query returned {len(results)} results")
        
        print("  [OK] KnowledgeCompiler tests passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] KnowledgeCompiler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_skill_contracts():
    """Test the SkillContractRegistry module."""
    print("\nTesting SkillContractRegistry...")
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    try:
        from core.skill_contracts import SkillContractRegistry, SkillContract, SkillInput, SkillOutput, SkillCheck
        
        # Initialize registry with temp directory
        registry = SkillContractRegistry(registry_dir=temp_dir)
        
        # Create a test skill contract
        test_contract = SkillContract(
            skill_id="test-skill-001",
            name="Test Analysis Skill",
            version="1.0.0",
            description="A test skill for analyzing data",
            domain="data_analysis",
            category="analysis",
            inputs=[
                SkillInput(name="data", type="json", required=True, description="Input data to analyze"),
                SkillInput(name="config", type="json", required=False, description="Configuration options")
            ],
            outputs=[
                SkillOutput(name="result", type="json", format="json", description="Analysis results"),
                SkillOutput(name="report", type="text", format="markdown", description="Human-readable report")
            ],
            procedure=[
                "Load input data",
                "Validate data format",
                "Perform analysis",
                "Generate results",
                "Create report"
            ],
            quality_checks=[
                SkillCheck(
                    check_id="check-001",
                    description="Verify output format",
                    verify="auto",
                    severity="high"
                )
            ],
            dependencies=[],
            tags=["analysis", "data", "test"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # Test registration
        success = registry.register(test_contract)
        assert success, "Registration failed"
        print("  [OK] Skill contract registered")
        
        # Test retrieval
        retrieved = registry.get("test-skill-001")
        assert retrieved is not None, "Retrieval failed"
        assert retrieved.name == "Test Analysis Skill"
        print("  [OK] Skill contract retrieved")
        
        # Test search by domain
        results = registry.search(domain="data_analysis")
        assert len(results) > 0
        print(f"  [OK] Domain search returned {len(results)} results")
        
        # Test search by category
        results = registry.search(category="analysis")
        assert len(results) > 0
        print(f"  [OK] Category search returned {len(results)} results")
        
        # Test search by tags
        results = registry.search(tags=["analysis"])
        assert len(results) > 0
        print(f"  [OK] Tag search returned {len(results)} results")
        
        # Test dependencies (empty)
        deps = registry.get_dependencies("test-skill-001")
        assert len(deps) == 0
        print("  [OK] Dependencies check passed")
        
        # Test composition
        composed = registry.compose(["test-skill-001"])
        assert len(composed) == 1
        print("  [OK] Composition test passed")
        
        # Test file storage
        assert os.path.exists(os.path.join(temp_dir, "test-skill-001.json"))
        print("  [OK] Skill contract stored to disk")
        
        # Test loading from disk
        new_registry = SkillContractRegistry(registry_dir=temp_dir)
        assert "test-skill-001" in new_registry.contracts
        print("  [OK] Skill contracts loaded from disk")
        
        print("  [OK] SkillContractRegistry tests passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] SkillContractRegistry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_integration():
    """Test integration between modules."""
    print("\nTesting integration...")
    
    temp_dir = tempfile.mkdtemp()
    try:
        from core.knowledge_compiler import KnowledgeCompiler
        from core.skill_contracts import SkillContractRegistry, SkillContract, SkillInput, SkillOutput, SkillCheck
        
        # Create compiler and registry
        compiler = KnowledgeCompiler(knowledge_dir=os.path.join(temp_dir, "knowledge"))
        registry = SkillContractRegistry(registry_dir=os.path.join(temp_dir, "skills"))
        
        # Compile some knowledge
        test_text = """
        Data analysis involves examining raw data to draw conclusions.
        Statistical analysis is a component of data analysis.
        Machine learning can automate data analysis tasks.
        """
        
        knowledge = compiler.compile_from_text(
            text=test_text,
            domain="data_science",
            source="integration_test"
        )
        
        # Create a skill that uses the knowledge
        skill = SkillContract(
            skill_id="data-analysis-skill",
            name="Data Analysis Skill",
            version="1.0.0",
            description="Analyzes data using compiled knowledge",
            domain="data_science",
            category="analysis",
            inputs=[
                SkillInput(name="dataset", type="json", required=True, description="Dataset to analyze")
            ],
            outputs=[
                SkillOutput(name="analysis_result", type="json", format="json", description="Analysis results")
            ],
            procedure=[
                "Load compiled knowledge for data_science domain",
                "Apply knowledge to dataset",
                "Generate analysis results"
            ],
            quality_checks=[
                SkillCheck(
                    check_id="integration-check-001",
                    description="Verify knowledge application",
                    verify="auto",
                    severity="high"
                )
            ],
            dependencies=[],
            tags=["data", "analysis", "integration"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # Register the skill
        registry.register(skill)
        
        # Verify both systems work together
        knowledge_results = compiler.query(domain="data_science")
        skill_results = registry.search(domain="data_science")
        
        assert len(knowledge_results) > 0
        assert len(skill_results) > 0
        
        print("  [OK] Integration test passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    print("=== Testing Knowledge Compiler and Skill Contracts ===\n")
    
    tests = [
        test_knowledge_compiler,
        test_skill_contracts,
        test_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [FAIL] Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n[OK] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Some tests failed!")
        sys.exit(1)