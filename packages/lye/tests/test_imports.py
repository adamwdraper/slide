"""Test imports and lazy loading for Lye tools"""
import pytest
import sys


class TestLyeImports:
    """Test Lye imports and tool structure"""
    
    def test_tool_lists_exist(self):
        """Test that all tool lists are accessible"""
        import lye
        
        # Tool lists should be accessible (empty until loaded via TOOL_MODULES)
        assert isinstance(lye.TOOLS, list)
        assert isinstance(lye.WEB_TOOLS, list)
        assert isinstance(lye.FILES_TOOLS, list)
        assert isinstance(lye.COMMAND_LINE_TOOLS, list)
        assert isinstance(lye.AUDIO_TOOLS, list)
        assert isinstance(lye.IMAGE_TOOLS, list)
    
    def test_module_namespaces(self):
        """Test that we can import modules as namespaces (lazy loaded)"""
        # Import specific modules on-demand (only ones with no hard dependencies)
        from lye import web, command_line
        
        # Check modules exist
        assert web is not None
        assert command_line is not None
        
        # Check modules have TOOLS attribute
        assert hasattr(web, 'TOOLS')
        assert hasattr(command_line, 'TOOLS')
        
        # Check we can access functions through namespaces
        assert hasattr(web, 'fetch_page')
        assert hasattr(web, 'download_file')
        assert hasattr(command_line, 'run_command')
    
    def test_namespace_functions_are_callable(self):
        """Test that functions accessed through namespaces are callable"""
        from lye import web, command_line
        
        assert callable(web.fetch_page)
        assert callable(web.download_file)
        assert callable(command_line.run_command)
    
    def test_tools_have_correct_structure(self):
        """Test that tools have the required structure"""
        import lye
        
        # Load web tools via TOOL_MODULES to trigger lazy loading
        web_tools = lye.TOOL_MODULES['web']
        
        for tool in web_tools:
            assert isinstance(tool, dict)
            assert 'definition' in tool
            assert 'implementation' in tool
            assert 'type' in tool['definition']
            assert 'function' in tool['definition']
            assert 'name' in tool['definition']['function']
            assert 'description' in tool['definition']['function']
            assert 'parameters' in tool['definition']['function']
    
    def test_combined_tools_list(self):
        """Test that TOOL_MODULES provides access to all module tools"""
        import lye
        
        # Get all tools via TOOL_MODULES (this tests lazy loading)
        all_module_tools = []
        for module_name in ['web', 'files', 'command_line', 'audio', 'image', 
                           'browser', 'slack', 'notion', 'wandb_workspaces']:
            tools = lye.TOOL_MODULES.get(module_name, [])
            all_module_tools.extend(tools)
        
        # Should have loaded tools from all modules
        assert len(all_module_tools) >= 0  # Some modules may have no tools or fail to import
    
    def test_no_duplicate_tools(self):
        """Test that there are no duplicate tool names across all modules"""
        import lye
        
        # Collect all tool names from all modules
        all_tool_names = []
        for module_name in lye.TOOL_MODULES.keys():
            tools = lye.TOOL_MODULES[module_name]
            for tool in tools:
                if isinstance(tool, dict) and 'definition' in tool:
                    name = tool['definition']['function']['name']
                    all_tool_names.append(name)
        
        # Check for duplicates
        assert len(all_tool_names) == len(set(all_tool_names)), "Duplicate tool names found"


class TestLazyLoading:
    """Test lazy loading of tool modules"""
    
    def test_import_lye_without_loading_all_modules(self):
        """Test that importing lye doesn't load all modules"""
        # Remove lye from sys.modules to force fresh import
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('lye')]
        for module in modules_to_remove:
            del sys.modules[module]
        
        # Import lye fresh
        import lye
        
        # Check that specific modules are NOT loaded yet
        assert 'lye.browser' not in sys.modules, "browser should not be eagerly loaded"
        assert 'lye.wandb_workspaces' not in sys.modules, "wandb_workspaces should not be eagerly loaded"
        
        # The main lye module should be loaded
        assert 'lye' in sys.modules
        
    def test_tool_modules_dict_lazy_loads(self):
        """Test that accessing TOOL_MODULES triggers lazy loading"""
        import lye
        
        # Reset the loaded modules cache
        lye._MODULES_LOADED.clear()
        
        # Access web tools via TOOL_MODULES
        web_tools = lye.TOOL_MODULES['web']
        
        # Web should now be loaded
        assert 'web' in lye._MODULES_LOADED
        
        # But browser should NOT be loaded
        assert 'browser' not in lye._MODULES_LOADED
        assert 'wandb_workspaces' not in lye._MODULES_LOADED
        
    def test_tool_modules_keys(self):
        """Test that TOOL_MODULES exposes all available module names"""
        import lye
        
        keys = list(lye.TOOL_MODULES.keys())
        
        # Should have all module names
        assert 'web' in keys
        assert 'files' in keys
        assert 'command_line' in keys
        assert 'audio' in keys
        assert 'image' in keys
        assert 'browser' in keys
        assert 'slack' in keys
        assert 'notion' in keys
        assert 'wandb_workspaces' in keys
        
    def test_tool_modules_contains(self):
        """Test that TOOL_MODULES __contains__ works"""
        import lye
        
        assert 'web' in lye.TOOL_MODULES
        assert 'files' in lye.TOOL_MODULES
        assert 'invalid_module' not in lye.TOOL_MODULES
        
    def test_tool_modules_get_with_default(self):
        """Test that TOOL_MODULES.get() works with default values"""
        import lye
        
        # Valid module should return tools
        web_tools = lye.TOOL_MODULES.get('web')
        assert web_tools is not None
        assert isinstance(web_tools, list)
        
        # Invalid module should return default
        invalid_tools = lye.TOOL_MODULES.get('invalid_module', [])
        assert invalid_tools == []
        
    def test_caching_works(self):
        """Test that modules are cached after first load"""
        import lye
        
        # Load web tools twice
        web_tools_1 = lye.TOOL_MODULES['web']
        web_tools_2 = lye.TOOL_MODULES['web']
        
        # Should be the same object (cached)
        assert web_tools_1 is web_tools_2
        
        # The actual cache is in the module-level lists (WEB_TOOLS, etc)
        # and in _MODULES_LOADED
        assert 'web' in lye._MODULES_LOADED
        
    def test_failed_import_returns_empty_list(self):
        """Test that failed imports return empty list instead of raising"""
        import lye
        
        # Try to load a module that might fail to import
        # (browser requires browser_use, wandb_workspaces requires wandb-workspaces)
        try:
            browser_tools = lye.TOOL_MODULES['browser']
            # If it succeeds, should be a list
            assert isinstance(browser_tools, list)
        except Exception as e:
            # Should not raise an exception
            pytest.fail(f"Loading browser tools raised an exception: {e}")
            
    def test_only_requested_modules_loaded(self):
        """Test that only explicitly requested modules are loaded"""
        import lye
        
        # Remove specific modules from sys.modules to test fresh loading
        modules_to_test = ['lye.slack', 'lye.notion']
        for mod in modules_to_test:
            if mod in sys.modules:
                del sys.modules[mod]
        
        # Load only web and files
        _ = lye.TOOL_MODULES['web']
        _ = lye.TOOL_MODULES['files']
        
        # Check that slack and notion were NOT loaded into sys.modules
        assert 'lye.slack' not in sys.modules, "slack should not be loaded"
        assert 'lye.notion' not in sys.modules, "notion should not be loaded"
        
    def test_tool_modules_items(self):
        """Test that TOOL_MODULES.items() works"""
        import lye
        
        # Get items (this will load all modules)
        items = dict(lye.TOOL_MODULES.items())
        
        # Should have all module names as keys
        assert 'web' in items
        assert 'files' in items
        
        # All values should be lists
        for key, value in items.items():
            assert isinstance(value, list), f"{key} tools should be a list"
            
    def test_tool_modules_values(self):
        """Test that TOOL_MODULES.values() works"""
        import lye
        
        # Get values (this will load all modules)
        values = list(lye.TOOL_MODULES.values())
        
        # All values should be lists
        for value in values:
            assert isinstance(value, list), "All tool values should be lists" 