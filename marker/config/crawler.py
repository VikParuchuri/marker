import importlib
import inspect
import pkgutil
from functools import cached_property
from typing import Annotated, Dict, Optional, Type, get_args, get_origin

from marker.builders import BaseBuilder
from marker.converters import BaseConverter
from marker.processors import BaseProcessor
from marker.providers import BaseProvider
from marker.renderers import BaseRenderer
from marker.util import camel_to_snake


class ConfigCrawler:
    def __init__(self, base_classes=(BaseBuilder, BaseProcessor, BaseConverter, BaseProvider, BaseRenderer)):
        self.base_classes = base_classes
        self.class_config_map = {}

        self._crawl_config()

    def _crawl_config(self):
        for base in self.base_classes:
            base_class_type = base.__name__.removeprefix('Base')
            self.class_config_map.setdefault(base_class_type, {})
            for class_name, class_type in self._find_subclasses(base).items():
                self.class_config_map[base_class_type].setdefault(class_name, {
                    'class_type': class_type,
                    'config': {}
                })
                for attr, attr_type in class_type.__annotations__.items():
                    default = getattr(class_type, attr)
                    metadata = (f"Default is {default}.",)

                    if get_origin(attr_type) is Annotated:
                        if any('Default' in desc for desc in attr_type.__metadata__):
                            metadata = attr_type.__metadata__
                        else:
                            metadata = attr_type.__metadata__ + metadata
                        attr_type = get_args(attr_type)[0]

                    formatted_type = self._format_type(attr_type)
                    self.class_config_map[base_class_type][class_name]['config'][attr] = (attr_type, formatted_type, default, metadata)

    @cached_property
    def attr_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for base_type_dict in self.class_config_map.values():
            for class_map in base_type_dict.values():
                for attr in class_map['config'].keys():
                    counts[attr] = counts.get(attr, 0) + 1
        return counts

    @cached_property
    def canonical_attr_map(self) -> Dict[str, str]:
        canonical_attr_map: Dict[str, str] = {}
        for base_type_dict in self.class_config_map.values():
            for class_name, class_map in base_type_dict.items():
                class_name_snake_case = camel_to_snake(class_name)
                for attr in class_map['config'].keys():
                    canonical_attr_map[attr] = attr
                    canonical_attr_map[f"{class_name_snake_case}_{attr}"] = attr
        return canonical_attr_map

    def validate_attr(self, attr_name: str, class_name: Optional[str] = None) -> bool:
        if class_name is None:
            # Look through all classes in all base types
            for base_type_dict in self.class_config_map.values():
                for class_map in base_type_dict.values():
                    if attr_name in class_map['config']:
                        return True
            return False
        else:
            # We need to find the class_name in *any* base_type
            for base_type_dict in self.class_config_map.values():
                if class_name in base_type_dict:
                    return attr_name in base_type_dict[class_name]['config']
            return False

    def _find_subclasses(self, base_class):
        subclasses = {base_class.__name__: base_class}
        module_name = base_class.__module__
        package = importlib.import_module(module_name)
        if hasattr(package, '__path__'):
            for _, module_name, _ in pkgutil.walk_packages(package.__path__, module_name + "."):
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, base_class) and obj is not base_class:
                            subclasses[name] = obj
                except ImportError:
                    pass
        return subclasses

    def _format_type(self, t: Type) -> str:
        """Format a typing type like Optional[int] into a readable string."""

        if get_origin(t):  # Handle Optional and types with origins separately
            return f"{t}".removeprefix('typing.')
        else:  # Regular types like int, str
            return t.__name__


crawler = ConfigCrawler()
