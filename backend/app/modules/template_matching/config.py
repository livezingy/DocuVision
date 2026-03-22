"""
Template Matching Module Configuration
"""

from pydantic import BaseModel


class TemplateMatchingConfig(BaseModel):
    """Template Matching模块配置"""
    enabled: bool = True
    templates_dir: str = "./templates"
    
    class Config:
        extra = "allow"
