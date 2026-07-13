from typing import Any, Dict
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult

# Normalization mapping for various unit aliases
UNIT_ALIASES = {
    # Temperature
    "c": "celsius", "celsius": "celsius", "°c": "celsius",
    "f": "fahrenheit", "fahrenheit": "fahrenheit", "°f": "fahrenheit",
    "k": "kelvin", "kelvin": "kelvin",
    
    # Length
    "m": "meters", "meter": "meters", "meters": "meters",
    "km": "kilometers", "kilometer": "kilometers", "kilometers": "kilometers",
    "mi": "miles", "mile": "miles", "miles": "miles",
    "ft": "feet", "foot": "feet", "feet": "feet",
    "in": "inches", "inch": "inches", "inches": "inches",
    
    # Weight
    "kg": "kilograms", "kilogram": "kilograms", "kilograms": "kilograms",
    "g": "grams", "gram": "grams", "grams": "grams",
    "lb": "pounds", "lbs": "pounds", "pound": "pounds", "pounds": "pounds",
    "oz": "ounces", "ounce": "ounces", "ounces": "ounces",
    
    # Speed
    "mps": "mps", "m/s": "mps", "meters per second": "mps",
    "kmh": "kmh", "km/h": "kmh", "kilometers per hour": "kmh",
    "mph": "mph", "miles per hour": "mph",
}

# Base conversion factors relative to a reference unit
# Reference units: meters (length), grams (weight), mps (speed)
LENGTH_FACTORS = {
    "meters": 1.0,
    "kilometers": 1000.0,
    "miles": 1609.344,
    "feet": 0.3048,
    "inches": 0.0254
}

WEIGHT_FACTORS = {
    "grams": 1.0,
    "kilograms": 1000.0,
    "pounds": 453.59237,
    "ounces": 28.349523125
}

SPEED_FACTORS = {
    "mps": 1.0,
    "kmh": 0.2777777777777778,  # 1 km/h = 1/3.6 m/s
    "mph": 0.44704               # 1 mph = 1609.344 / 3600 m/s
}

class UnitConverterInput(BaseModel):
    value: float = Field(..., description="The numeric value to convert.")
    from_unit: str = Field(..., description="The unit of the input value (e.g. 'celsius', 'miles', 'kg', 'mph').")
    to_unit: str = Field(..., description="The target unit to convert to (e.g. 'fahrenheit', 'kilometers', 'lbs', 'kmh').")

class UnitConverterTool(BaseTool):
    name: str = "unit_converter"
    description: str = (
        "Perform offline unit conversions for temperature (celsius, fahrenheit, kelvin), "
        "length/distance (meters, kilometers, miles, feet, inches), "
        "weight/mass (grams, kilograms, pounds, ounces), and speed (mps, kmh, mph)."
    )
    input_schema: Any = UnitConverterInput
    permission_level: str = "safe"
    timeout_seconds: int = 5

    async def execute(self, value: float, from_unit: str, to_unit: str, **kwargs) -> ToolResult:
        u_from = UNIT_ALIASES.get(from_unit.strip().lower())
        u_to = UNIT_ALIASES.get(to_unit.strip().lower())
        
        if not u_from or not u_to:
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": f"Unsupported or unknown units: '{from_unit}' or '{to_unit}'."}
            )

        # 1. Temperature Conversion
        temp_units = {"celsius", "fahrenheit", "kelvin"}
        if u_from in temp_units or u_to in temp_units:
            if u_from not in temp_units or u_to not in temp_units:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Cannot convert between temperature unit '{from_unit}' and non-temperature unit '{to_unit}'."}
                )
            
            # Normalize to Celsius first
            if u_from == "celsius":
                c = value
            elif u_from == "fahrenheit":
                c = (value - 32.0) * 5.0 / 9.0
            else: # kelvin
                c = value - 273.15
                
            # Convert from Celsius to destination
            if u_to == "celsius":
                res = c
            elif u_to == "fahrenheit":
                res = (c * 9.0 / 5.0) + 32.0
            else: # kelvin
                res = c + 273.15
                
            return ToolResult(success=True, data={"result": round(res, 4), "from_unit": u_from, "to_unit": u_to})

        # 2. Length Conversion
        if u_from in LENGTH_FACTORS or u_to in LENGTH_FACTORS:
            if u_from not in LENGTH_FACTORS or u_to not in LENGTH_FACTORS:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Cannot convert between length unit '{from_unit}' and non-length unit '{to_unit}'."}
                )
            
            meters = value * LENGTH_FACTORS[u_from]
            res = meters / LENGTH_FACTORS[u_to]
            return ToolResult(success=True, data={"result": round(res, 4), "from_unit": u_from, "to_unit": u_to})

        # 3. Weight Conversion
        if u_from in WEIGHT_FACTORS or u_to in WEIGHT_FACTORS:
            if u_from not in WEIGHT_FACTORS or u_to not in WEIGHT_FACTORS:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Cannot convert between weight unit '{from_unit}' and non-weight unit '{to_unit}'."}
                )
            
            grams = value * WEIGHT_FACTORS[u_from]
            res = grams / WEIGHT_FACTORS[u_to]
            return ToolResult(success=True, data={"result": round(res, 4), "from_unit": u_from, "to_unit": u_to})

        # 4. Speed Conversion
        if u_from in SPEED_FACTORS or u_to in SPEED_FACTORS:
            if u_from not in SPEED_FACTORS or u_to not in SPEED_FACTORS:
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": f"Cannot convert between speed unit '{from_unit}' and non-speed unit '{to_unit}'."}
                )
            
            mps = value * SPEED_FACTORS[u_from]
            res = mps / SPEED_FACTORS[u_to]
            return ToolResult(success=True, data={"result": round(res, 4), "from_unit": u_from, "to_unit": u_to})

        return ToolResult(
            success=False,
            error="INVALID_ARGUMENTS",
            metadata={"error_detail": f"Units '{from_unit}' and '{to_unit}' are not in the same category."}
        )
