"""
Prompt Loader Service

Loads and manages externalized prompts from JSON files.
All prompts must be defined in prompts.json - no code fallbacks.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

_logger = logging.getLogger(__name__)


class PromptLoader:
    """Loads prompts from external JSON file"""
    
    def __init__(self, prompts_file: Optional[str] = None):
        """
        Initialize prompt loader
        
        Args:
            prompts_file: Path to prompts JSON file. If None, uses default from config.
        """
        from app.core.config import settings
        
        if prompts_file is None:
            # Default: use path from config, or fallback to app/prompts/prompts.json
            prompts_file = getattr(settings, 'PROMPTS_FILE', 'app/prompts/prompts.json')
        
        # Resolve path relative to backend directory
        if not os.path.isabs(prompts_file):
            backend_dir = Path(__file__).parent.parent.parent
            self.prompts_file = backend_dir / prompts_file
        else:
            self.prompts_file = Path(prompts_file)
        
        self._prompts: Dict[str, Any] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """Load prompts from JSON file"""
        try:
            if not self.prompts_file.exists():
                error_msg = f"Prompts file not found: {self.prompts_file}. Please create it with all required prompts."
                _logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                self._prompts = json.load(f)
            
            _logger.info(f"✅ Loaded prompts from {self.prompts_file}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in prompts file {self.prompts_file}: {e}"
            _logger.error(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"Error loading prompts file {self.prompts_file}: {e}"
            _logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def get_prompt(self, category: str, key: str, **kwargs) -> str:
        """
        Get a prompt by category and key, with optional template variables
        
        Args:
            category: Prompt category (e.g., 'sql_maker', 'followup_agent')
            key: Prompt key within category (e.g., 'system_prompt', 'user_prompt_template')
            **kwargs: Template variables to substitute in the prompt using .format()
        
        Returns:
            Prompt string with variables substituted
        
        Raises:
            KeyError: If prompt category or key is not found
            ValueError: If template variable substitution fails
        """
        try:
            category_prompts = self._prompts.get(category)
            if category_prompts is None:
                raise KeyError(f"Prompt category '{category}' not found in prompts.json")
            
            prompt = category_prompts.get(key)
            if prompt is None:
                raise KeyError(f"Prompt key '{key}' not found in category '{category}'")
            
            # Substitute template variables if provided
            if kwargs:
                try:
                    prompt = prompt.format(**kwargs)
                except KeyError as e:
                    error_msg = f"Missing template variable {e} in prompt {category}.{key}"
                    _logger.error(error_msg)
                    raise ValueError(error_msg) from e
                except Exception as e:
                    error_msg = f"Error formatting prompt {category}.{key}: {e}"
                    _logger.error(error_msg)
                    raise ValueError(error_msg) from e
            
            return prompt
        except KeyError:
            raise
        except Exception as e:
            error_msg = f"Error getting prompt {category}.{key}: {e}"
            _logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def get_prompt_dict(self, category: str) -> Dict[str, Any]:
        """
        Get all prompts for a category
        
        Returns:
            Dictionary of prompts for the category
        
        Raises:
            KeyError: If category is not found
        """
        category_prompts = self._prompts.get(category)
        if category_prompts is None:
            raise KeyError(f"Prompt category '{category}' not found in prompts.json")
        return category_prompts
    
    def reload(self):
        """Reload prompts from file (useful for hot-reloading during development)"""
        self._load_prompts()
        _logger.info("Prompts reloaded from file")


# Singleton instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get singleton prompt loader instance"""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader
