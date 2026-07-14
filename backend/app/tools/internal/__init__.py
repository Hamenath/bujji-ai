from app.tools.registry import tool_registry
from app.tools.internal.echo import EchoTool
from app.tools.internal.datetime_tool import DateTimeTool
from app.tools.internal.calculator import CalculatorTool
from app.tools.web.web_search import WebSearchTool
from app.tools.web.webpage_reader import WebpageReaderTool
from app.tools.internal.weather import WeatherTool, GeocodePlaceTool, WeatherCurrentTool, WeatherForecastTool
from app.tools.internal.world_time import WorldTimeTool
from app.tools.internal.unit_converter import UnitConverterTool
from app.tools.internal.date_calculator import DateCalculatorTool

def register_internal_tools():
    """Auto-registers all safe tools in the tool registry."""
    try:
        tool_registry.register(EchoTool())
    except ValueError:
        pass  # Already registered

    try:
        tool_registry.register(DateTimeTool())
    except ValueError:
        pass

    try:
        tool_registry.register(CalculatorTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WebSearchTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WebpageReaderTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WeatherTool())
    except ValueError:
        pass

    try:
        tool_registry.register(GeocodePlaceTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WeatherCurrentTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WeatherForecastTool())
    except ValueError:
        pass

    try:
        tool_registry.register(WorldTimeTool())
    except ValueError:
        pass

    try:
        tool_registry.register(UnitConverterTool())
    except ValueError:
        pass

    try:
        tool_registry.register(DateCalculatorTool())
    except ValueError:
        pass

