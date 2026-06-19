import importlib
import logging
import pkgutil

from .base import ToolPlugin, ToolContext

logger = logging.getLogger(__name__)

_registry: dict[str, ToolPlugin] = {}


def register(plugin: ToolPlugin):
    _registry[plugin.name] = plugin


def _discover():
    for _, modname, _ in pkgutil.iter_modules(__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            module = importlib.import_module(f".{modname}", __package__)
        except ImportError as e:
            logger.warning("Skipping plugin %s: %s", modname, e)
            continue
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ToolPlugin)
                and attr is not ToolPlugin
                and attr.name
            ):
                register(attr())


def get_definitions() -> list[dict]:
    return [p.to_definition() for p in _registry.values()]


def get_plugin(name: str) -> ToolPlugin | None:
    return _registry.get(name)


def list_plugins() -> list[str]:
    return list(_registry.keys())


def execute(name: str, tool_input: dict, context: ToolContext) -> str:
    plugin = _registry.get(name)
    if not plugin:
        return f"Unknown tool: {name}"
    try:
        logger.info("Tool call: %s(%s)", name, str(tool_input)[:200])
        return plugin.execute(tool_input, context)
    except Exception as e:
        logger.exception("Tool execution error: %s", name)
        return f"Error: {e}"


_discover()
logger.info("Loaded %d plugins: %s", len(_registry), ", ".join(_registry.keys()))
