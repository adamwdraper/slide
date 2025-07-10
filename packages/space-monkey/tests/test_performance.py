"""
Performance tests for space_monkey.

These tests ensure that the template generation is efficient and scales well.
"""

import pytest
import time
from space_monkey.templates import TemplateManager


class TestTemplatePerformance:
    """Test template generation performance."""
    
    def test_template_manager_initialization_time(self):
        """Test that TemplateManager initializes quickly."""
        start_time = time.time()
        manager = TemplateManager()
        end_time = time.time()
        
        initialization_time = end_time - start_time
        # Should initialize in under 1 second
        assert initialization_time < 1.0
    
    def test_basic_agent_generation_time(self):
        """Test that basic agent generation is fast."""
        manager = TemplateManager()
        
        start_time = time.time()
        files = manager.generate_agent(
            agent_name="PerformanceBot",
            description="Testing performance"
        )
        end_time = time.time()
        
        generation_time = end_time - start_time
        # Should generate in under 0.1 seconds
        assert generation_time < 0.1
        assert isinstance(files, dict)
    
    def test_complex_agent_generation_time(self):
        """Test that complex agent generation with many options is still fast."""
        manager = TemplateManager()
        
        start_time = time.time()
        files = manager.generate_agent(
            agent_name="ComplexPerformanceBot",
            description="Testing performance with complex configuration",
            tools=["notion:notion-search", "slack:send-message", "web:search", "db:query"],
            sub_agents=["Agent1", "Agent2", "Agent3", "Agent4", "Agent5"],
            citations_required=True,
            specific_guidelines="Complex guidelines for performance testing",
            bot_user_id=True
        )
        end_time = time.time()
        
        generation_time = end_time - start_time
        # Should still generate in under 0.2 seconds even with complexity
        assert generation_time < 0.2
        assert isinstance(files, dict)
    
    def test_multiple_agent_generation_performance(self):
        """Test generating multiple agents in sequence."""
        manager = TemplateManager()
        
        start_time = time.time()
        
        # Generate 10 agents
        for i in range(10):
            files = manager.generate_agent(
                agent_name=f"Bot{i}",
                description=f"Performance test bot {i}",
                tools=["notion:search"],
                bot_user_id=True
            )
            assert isinstance(files, dict)
        
        end_time = time.time()
        
        total_time = end_time - start_time
        # Should generate 10 agents in under 1 second total
        assert total_time < 1.0
        
        # Average time per agent should be under 0.1 seconds
        avg_time = total_time / 10
        assert avg_time < 0.1
    
    def test_template_loading_performance(self):
        """Test that template loading doesn't significantly impact performance."""
        # Test multiple initializations
        start_time = time.time()
        
        for _ in range(5):
            manager = TemplateManager()
            assert manager is not None
        
        end_time = time.time()
        
        total_time = end_time - start_time
        # Should create 5 managers in under 0.5 seconds
        assert total_time < 0.5


class TestMemoryUsage:
    """Test memory usage of template generation."""
    
    def test_template_manager_memory_reuse(self):
        """Test that TemplateManager can be reused efficiently."""
        manager = TemplateManager()
        
        # Generate multiple agents with same manager
        for i in range(20):
            files = manager.generate_agent(
                agent_name=f"MemoryBot{i}",
                description="Testing memory usage"
            )
            assert isinstance(files, dict)
        
        # Should complete without memory issues
        assert True
    
    def test_large_agent_generation(self):
        """Test generating agents with large configurations."""
        manager = TemplateManager()
        
        # Create large lists of tools and sub-agents
        tools = [f"tool{i}:action" for i in range(50)]
        sub_agents = [f"SubAgent{i}" for i in range(20)]
        
        files = manager.generate_agent(
            agent_name="LargeBot",
            description="Testing large configuration handling",
            tools=tools,
            sub_agents=sub_agents,
            bot_user_id=True,
            citations_required=True
        )
        
        assert isinstance(files, dict)
        
        # Check that generated content handles large lists
        if "agent.py" in files:
            content = files["agent.py"]
            assert "tool0:action" in content
            assert "tool49:action" in content
            assert "subagent0_agent" in content  # Sub-agent names get converted to snake_case
            assert "subagent19_agent" in content


class TestScalability:
    """Test scalability of template system."""
    
    def test_concurrent_template_generation(self):
        """Test that template generation works with concurrent access."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def generate_agent(agent_id):
            try:
                manager = TemplateManager()
                files = manager.generate_agent(
                    agent_name=f"ConcurrentBot{agent_id}",
                    description=f"Concurrent generation test {agent_id}"
                )
                results.put(("success", agent_id, files))
            except Exception as e:
                results.put(("error", agent_id, str(e)))
        
        # Start 5 concurrent generations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=generate_agent, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = 0
        while not results.empty():
            status, agent_id, data = results.get()
            if status == "success":
                success_count += 1
                assert isinstance(data, dict)
        
        # All should succeed
        assert success_count == 5


if __name__ == "__main__":
    pytest.main([__file__]) 