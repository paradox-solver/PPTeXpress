import os
from pathlib import Path


class TemplateLoader:
    def __init__(self, template_dir="templates"):
        self.template_dir = Path(template_dir)

    def load_template(self, template_name):
        """Load template file"""
        template_path = self.template_dir / template_name
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            raise FileNotFoundError(f"Template file does not exist: {template_path}")

    def render_template(self, template_name, **context):
        """render template"""
        template = self.load_template(template_name)

        # Simple template variable replacement
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            template = template.replace(placeholder, str(value))

        return template


# Create a global template loader
template_loader = TemplateLoader()
