import weave
from typing import Optional, Dict, List, Any, Union
from lye.utils.logging import get_logger

logger = get_logger(__name__)

@weave.op(name="wandb-create_workspace")
def create_workspace(
    *,
    name: str,
    entity: str,
    project: str,
    sections: Optional[List[Dict[str, Any]]] = None,
    description: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new Weights & Biases workspace programmatically.
    
    Args:
        name (str): Name of the workspace
        entity (str): W&B entity (username or team name)
        project (str): W&B project name
        sections (List[Dict], optional): List of section configurations
        description (str, optional): Description of the workspace
        settings (Dict, optional): Workspace-level settings
    
    Returns:
        Dict: Response with workspace creation status and details
    """
    try:
        import wandb_workspaces.workspaces as ws
        
        # Try to import panel classes
        panel_classes = {}
        try:
            import wandb_workspaces.reports.v2 as v2
            panel_classes = {
                "line": getattr(v2, "LinePlot", None),
                "scalar": getattr(v2, "ScalarChart", None),
                "bar": getattr(v2, "BarChart", None),
            }
        except ImportError:
            # Try alternative import paths
            try:
                # Try importing from main reports module
                import wandb_workspaces.reports as wr
                # Check if v2 is available as attribute
                if hasattr(wr, 'v2'):
                    v2 = wr.v2
                    panel_classes = {
                        "line": getattr(v2, "LinePlot", None),
                        "scalar": getattr(v2, "ScalarChart", None),
                        "bar": getattr(v2, "BarChart", None),
                    }
            except ImportError:
                pass
        
        # Create sections if provided
        workspace_sections = []
        if sections:
            for section_config in sections:
                # Process panels
                processed_panels = []
                raw_panels = section_config.get("panels", [])
                
                for panel in raw_panels:
                    # If panel is already an object, use it directly
                    if hasattr(panel, "__class__") and hasattr(panel.__class__, "__module__"):
                        processed_panels.append(panel)
                    # If panel is a dict with panel_type, try to create it
                    elif isinstance(panel, dict) and "panel_type" in panel:
                        panel_type = panel["panel_type"]
                        panel_class = panel_classes.get(panel_type)
                        
                        if panel_class:
                            # Extract relevant args for panel creation
                            panel_args = {k: v for k, v in panel.items() if k not in ["panel_type", "plot_type", "chart_type", "success", "error"]}
                            if "plot_config" in panel:
                                panel_args.update(panel["plot_config"])
                            if "chart_config" in panel:
                                panel_args.update(panel["chart_config"])
                                
                            try:
                                panel_obj = panel_class(**panel_args)
                                processed_panels.append(panel_obj)
                            except Exception as e:
                                logger.warning(f"Could not create {panel_type} panel: {e}")
                                # Add as raw config if creation fails
                                processed_panels.append(panel)
                        else:
                            # Add as raw config if class not found
                            processed_panels.append(panel)
                    # If panel has plot_object, use that
                    elif isinstance(panel, dict) and "plot_object" in panel:
                        processed_panels.append(panel["plot_object"])
                    # If panel has chart_object, use that
                    elif isinstance(panel, dict) and "chart_object" in panel:
                        processed_panels.append(panel["chart_object"])
                    else:
                        # Add as is
                        processed_panels.append(panel)
                
                section = ws.Section(
                    name=section_config.get("name", "Untitled Section"),
                    panels=processed_panels,
                    is_open=section_config.get("is_open", True)
                )
                workspace_sections.append(section)
        
        # Create workspace
        workspace = ws.Workspace(
            name=name,
            entity=entity,
            project=project,
            sections=workspace_sections
        )
        
        # Apply settings if provided
        if settings:
            for key, value in settings.items():
                setattr(workspace, key, value)
        
        # Save workspace
        result = workspace.save()
        
        return {
            "success": True,
            "workspace_name": name,
            "entity": entity,
            "project": project,
            "workspace_id": getattr(result, 'id', None),
            "url": getattr(result, 'url', None),
            "description": description,
            "error": None
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error creating workspace: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="wandb-load_workspace")
def load_workspace(*, url: str) -> Dict[str, Any]:
    """
    Load an existing workspace from a W&B URL.
    
    Args:
        url (str): The W&B workspace URL
    
    Returns:
        Dict: Workspace data and metadata
    """
    try:
        import wandb_workspaces.workspaces as ws
        
        workspace = ws.Workspace.from_url(url)
        
        return {
            "success": True,
            "workspace_name": workspace.name,
            "entity": workspace.entity,
            "project": workspace.project,
            "description": getattr(workspace, 'description', None),
            "sections_count": len(workspace.sections) if workspace.sections else 0,
            "url": url,
            "error": None
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error loading workspace: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="wandb-create_line_plot")
def create_line_plot(
    *,
    x: str,
    y: Union[str, List[str]],
    title: Optional[str] = None,
    color_by: Optional[str] = None,
    smoothing: Optional[float] = None
) -> Dict[str, Any]:
    """
    Create a line plot configuration for a workspace section.
    
    Args:
        x (str): X-axis metric name
        y (Union[str, List[str]]): Y-axis metric name(s)
        title (str, optional): Plot title
        color_by (str, optional): Metric to color lines by
        smoothing (float, optional): Smoothing factor (0-1)
    
    Returns:
        Dict: Line plot configuration
    """
    try:
        import wandb_workspaces.reports.v2 as v2
        
        # Ensure y is a list
        y_metrics = [y] if isinstance(y, str) else y
        
        # Create panel arguments
        panel_args = {
            "x": x,
            "y": y_metrics
        }
        
        if title:
            panel_args["title"] = title
        if color_by:
            panel_args["color_by"] = color_by
        if smoothing is not None:
            panel_args["smoothing"] = smoothing
        
        # Try to create the actual panel object
        try:
            plot = v2.LinePlot(**panel_args)
            return {
                "success": True,
                "plot_type": "line_plot",
                "plot_config": panel_args,
                "plot_object": plot,
                "error": None
            }
        except AttributeError:
            # If LinePlot doesn't exist, return config for manual creation
            return {
                "success": True,
                "plot_type": "line_plot",
                "plot_config": panel_args,
                "panel_type": "line",
                "error": None
            }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error creating line plot: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="wandb-create_scalar_chart")
def create_scalar_chart(
    *,
    metric: str,
    title: Optional[str] = None,
    groupby: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a scalar chart configuration for a workspace section.
    
    Args:
        metric (str): Metric name to display
        title (str, optional): Chart title
        groupby (str, optional): Group results by this field
    
    Returns:
        Dict: Scalar chart configuration
    """
    try:
        import wandb_workspaces.reports.v2 as v2
        
        # Create panel arguments
        panel_args = {
            "metric": metric
        }
        
        if title:
            panel_args["title"] = title
        if groupby:
            panel_args["groupby"] = groupby
        
        # Try to create the actual panel object
        try:
            chart = v2.ScalarChart(**panel_args)
            return {
                "success": True,
                "chart_type": "scalar_chart",
                "chart_config": panel_args,
                "chart_object": chart,
                "error": None
            }
        except AttributeError:
            # If ScalarChart doesn't exist, return config for manual creation
            return {
                "success": True,
                "chart_type": "scalar_chart",
                "chart_config": panel_args,
                "panel_type": "scalar",
                "error": None
            }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error creating scalar chart: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="wandb-create_run_filter")
def create_run_filter(
    *,
    filters: Dict[str, Any],
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a run filter configuration for workspace sections.
    
    Args:
        filters (Dict): Filter criteria (e.g., {"accuracy": {"$gt": 0.9}})
        sort_by (str, optional): Metric to sort by
        sort_order (str): Sort order - "asc" or "desc"
        limit (int, optional): Maximum number of runs to include
    
    Returns:
        Dict: Run filter configuration
    """
    try:
        import wandb_workspaces.workspaces as ws
        
        # Create RunsetSettings with filters
        runset_settings = ws.RunsetSettings(
            filters=filters,
            sort=sort_by,
            order=sort_order,
            limit=limit
        )
        
        return {
            "success": True,
            "filter_config": {
                "filters": filters,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit
            },
            "runset_settings": runset_settings,
            "error": None
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error creating run filter: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@weave.op(name="wandb-save_workspace_view")
def save_workspace_view(
    *,
    workspace_url: str,
    view_name: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Save an existing workspace or view as a new view.
    
    Args:
        workspace_url (str): URL of an existing workspace or saved view
        view_name (str): Name for the new view
        description (str, optional): Description of the view
    
    Returns:
        Dict: View creation status and details
    
    Note:
        The workspace_url must be one of:
        - A saved view URL: https://wandb.ai/entity/project?nw=viewid
        - A workspace URL: https://wandb.ai/entity/project/workspace/workspace-name
        
        To save visualizations, first create a workspace using wandb-create_workspace,
        save it, then use the resulting URL with this function.
    """
    try:
        import wandb_workspaces.workspaces as ws
        
        # Validate URL format - W&B expects saved view URLs with ?nw= parameter
        if "?" not in workspace_url and "/workspace/" not in workspace_url:
            return {
                "success": False,
                "error": "Invalid workspace URL. Expected a saved view URL (e.g., https://wandb.ai/entity/project?nw=abc123) or workspace URL. You provided a project URL instead."
            }
        
        # Load existing workspace
        workspace = ws.Workspace.from_url(workspace_url)
        
        # Save as new view
        result = workspace.save_as_new_view(
            name=view_name,
            description=description
        )
        
        return {
            "success": True,
            "view_name": view_name,
            "description": description,
            "original_workspace_url": workspace_url,
            "new_view_url": getattr(result, 'url', None),
            "error": None
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb_workspaces package not installed. Install with: pip install wandb-workspaces"
        }
    except Exception as e:
        logger.error(f"Error saving workspace view: {e}")
        error_msg = str(e)
        if "not found" in error_msg.lower():
            error_msg += ". Make sure you're providing a valid workspace URL (not a project URL). You may need to create a workspace first using wandb-create_workspace."
        return {
            "success": False,
            "error": error_msg
        }

@weave.op(name="wandb-get_project_runs")
def get_project_runs(
    *,
    entity: str,
    project: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get runs from a W&B project with optional filtering.
    
    Args:
        entity (str): W&B entity (username or team name)
        project (str): W&B project name
        filters (Dict, optional): Filter criteria for runs
        limit (int): Maximum number of runs to return
    
    Returns:
        Dict: Project runs data and metadata
    """
    try:
        import wandb
        
        # Initialize API
        api = wandb.Api()
        
        # Get project runs
        runs = api.runs(f"{entity}/{project}", filters=filters)
        
        # Extract run data (limited to avoid large responses)
        run_data = []
        for i, run in enumerate(runs):
            if i >= limit:
                break
            
            # Handle created_at which might be a string or datetime
            created_at = run.created_at
            if created_at:
                if hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()
                else:
                    created_at = str(created_at)
            else:
                created_at = None
            
            run_info = {
                "id": run.id,
                "name": run.name,
                "state": run.state,
                "config": dict(run.config),
                "summary": dict(run.summary),
                "url": run.url,
                "created_at": created_at,
                "tags": run.tags,
                "group": run.group
            }
            run_data.append(run_info)
        
        return {
            "success": True,
            "entity": entity,
            "project": project,
            "runs_count": len(run_data),
            "runs": run_data,
            "filters_applied": filters,
            "error": None
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "wandb package not installed. Install with: pip install wandb"
        }
    except Exception as e:
        logger.error(f"Error getting project runs: {e}")
        return {
            "success": False,
            "error": str(e)
        }

TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-create_workspace",
                "description": "Create a new Weights & Biases workspace programmatically with sections and panels for experiment visualization.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the workspace"
                        },
                        "entity": {
                            "type": "string",
                            "description": "W&B entity (username or team name)"
                        },
                        "project": {
                            "type": "string",
                            "description": "W&B project name"
                        },
                        "sections": {
                            "type": "array",
                            "description": "List of section configurations with panels",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "panels": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                        "description": "List of panel objects (created with wandb-create_line_plot, wandb-create_scalar_chart, etc.)"
                                    },
                                    "is_open": {"type": "boolean"}
                                }
                            }
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the workspace"
                        },
                        "settings": {
                            "type": "object",
                            "description": "Workspace-level settings"
                        }
                    },
                    "required": ["name", "entity", "project"]
                }
            }
        },
        "implementation": create_workspace
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-load_workspace",
                "description": "Load an existing workspace from a W&B URL to inspect or modify it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The W&B workspace URL"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        "implementation": load_workspace
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-create_line_plot",
                "description": "Create a line plot configuration for workspace sections to visualize metrics over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "string",
                            "description": "X-axis metric name (e.g., 'Step', 'epoch')"
                        },
                        "y": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ],
                            "description": "Y-axis metric name(s) (e.g., 'loss', ['train_loss', 'val_loss'])"
                        },
                        "title": {
                            "type": "string",
                            "description": "Plot title"
                        },
                        "color_by": {
                            "type": "string",
                            "description": "Metric to color lines by"
                        },
                        "smoothing": {
                            "type": "number",
                            "description": "Smoothing factor between 0 and 1"
                        }
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "implementation": create_line_plot
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-create_scalar_chart",
                "description": "Create a scalar chart configuration for workspace sections to display single metric values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "Metric name to display (e.g., 'accuracy', 'final_loss')"
                        },
                        "title": {
                            "type": "string",
                            "description": "Chart title"
                        },
                        "groupby": {
                            "type": "string",
                            "description": "Group results by this field (e.g., 'config.model_type')"
                        }
                    },
                    "required": ["metric"]
                }
            }
        },
        "implementation": create_scalar_chart
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-create_run_filter",
                "description": "Create a run filter configuration to control which runs are displayed in workspace sections.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Filter criteria using W&B filter syntax (e.g., {'accuracy': {'$gt': 0.9}})"
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Metric to sort by (e.g., 'accuracy', 'loss')"
                        },
                        "sort_order": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort order - ascending or descending"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of runs to include"
                        }
                    },
                    "required": ["filters"]
                }
            }
        },
        "implementation": create_run_filter
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-save_workspace_view",
                "description": "Save an existing workspace as a new view. Requires a workspace URL (not a project URL). Create a workspace first using wandb-create_workspace if needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace_url": {
                            "type": "string",
                            "description": "URL of existing workspace or saved view (e.g., https://wandb.ai/entity/project?nw=viewid)"
                        },
                        "view_name": {
                            "type": "string",
                            "description": "Name for the new view"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the view"
                        }
                    },
                    "required": ["workspace_url", "view_name"]
                }
            }
        },
        "implementation": save_workspace_view
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb-get_project_runs",
                "description": "Retrieve runs from a W&B project with optional filtering for analysis and workspace creation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "W&B entity (username or team name)"
                        },
                        "project": {
                            "type": "string",
                            "description": "W&B project name"
                        },
                        "filters": {
                            "type": "object",
                            "description": "Filter criteria for runs using W&B filter syntax"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of runs to return",
                            "default": 100
                        }
                    },
                    "required": ["entity", "project"]
                }
            }
        },
        "implementation": get_project_runs
    }
]