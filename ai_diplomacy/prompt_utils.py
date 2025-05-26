# Removed comment: # Added to resolve NameError: name 'List' is not defined
import os
import jinja2

def load_prompt(filename: str) -> str:
    """Load a prompt from a file located in the 'prompts' subdirectory
    relative to the current script file."""
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(current_script_dir, "prompts", filename)

    if not os.path.exists(filepath):
        # For debugging, let's also check the CWD based path as a fallback
        # as this was part of the original complex logic.
        # This helps understand if the script is being run from an unexpected CWD.
        cwd_path = os.path.join(os.getcwd(), "prompts", filename)
        
        # Also check project root based path (assuming prompt_utils.py is in ai_diplomacy/
        # and prompts/ is at the project root: <project_root>/prompts/)
        project_root_prompts_path = os.path.join(os.path.dirname(current_script_dir), "prompts", filename)

        raise FileNotFoundError(
            f"Prompt file '{filename}' not found. \n"
            f"Expected at: {filepath} (relative to script: {current_script_dir})\n"
            f"Also checked CWD-based: {cwd_path} (CWD: {os.getcwd()})\n"
            f"Also checked project_root-based: {project_root_prompts_path}"
        )

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def render_prompt(template_filename: str, **kwargs) -> str:
    '''Loads a prompt template file and renders it using Jinja2.'''
    template_string = load_prompt(template_filename) # Removed comment: # Uses the existing load_prompt in this file
    if template_string is None:
        # load_prompt already logs an error and raises FileNotFoundError
        raise FileNotFoundError(f"Template file {template_filename} not found by load_prompt.")
    
    try:
        template = jinja2.Template(template_string)
        return template.render(**kwargs)
    except jinja2.TemplateSyntaxError as e:
        # Log or handle syntax errors in templates
        # For now, re-raise to make it visible
        raise Exception(f"Jinja2 template syntax error in {template_filename}: {e}") from e
    except Exception as e:
        raise Exception(f"Error rendering Jinja2 template {template_filename}: {e}") from e