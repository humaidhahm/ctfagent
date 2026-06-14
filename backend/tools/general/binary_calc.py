import re
from backend.tools.base import BaseTool
from loguru import logger


class BinaryCalcTool(BaseTool):
    name = "binary_calc"
    description = "Evaluate a binary operation expression (e.g., '1010 & 0110', '1010 | 0110', '~1010', '1010 << 2', '1010 >> 2', '1010 + 0110'). Returns the result WITHOUT leading zeros. For bitwise NOT (~) use the full padded form like ~0010 to get 1101."
    parameters = {
        "expression": {"type": "string", "description": "Binary expression to evaluate, e.g. '1010 & 0110' or '~1010'"},
    }

    def _to_int(self, s: str) -> int:
        return int(s, 2) if s else 0

    def _to_bin(self, n: int) -> str:
        if n < 0:
            n = n & 0xFFFFFFFF
        return bin(n)[2:]

    async def run(self, expression: str = "", **kwargs) -> dict:
        expression = kwargs.pop("expression", expression) or expression
        if not expression:
            return {"success": False, "output": "", "error": "No expression provided"}

        expression = expression.strip()
        # Strip 0b/0B prefix if present (LLM often adds it)
        expression = re.sub(r'\b0[bB](\d+)', r'\1', expression)
        try:
            # Match patterns: binary op binary, ~binary
            m = re.match(r'^(\d+)\s*([&|^+\-*/%]|<<|>>)\s*(\d+)$', expression)
            if m:
                a = self._to_int(m.group(1))
                op = m.group(2)

                if op in ('<<', '>>'):
                    b = int(m.group(3))
                else:
                    b = self._to_int(m.group(3))

                if op == '&':
                    result = a & b
                elif op == '|':
                    result = a | b
                elif op == '^':
                    result = a ^ b
                elif op == '+':
                    result = a + b
                elif op == '-':
                    result = a - b
                elif op == '*':
                    result = a * b
                elif op == '/' or op == '//':
                    result = a // b if b != 0 else 0
                elif op == '%':
                    result = a % b
                elif op == '<<':
                    result = a << b
                elif op == '>>':
                    result = a >> b
                else:
                    return {"success": False, "output": "", "error": f"Unknown operator: {op}"}

                result_str = self._to_bin(result)
                logger.info(f"binary_calc: {expression} = {result_str} (dec: {result})")
                return {
                    "success": True,
                    "output": result_str,
                    "decimal": result,
                    "expression": expression,
                }

            # ~binary (bitwise NOT)
            m = re.match(r'^~\s*(\d+)$', expression)
            if m:
                a = self._to_int(m.group(1))
                bit_width = len(m.group(1))
                result = (~a) & ((1 << bit_width) - 1)
                result_str = bin(result)[2:].zfill(bit_width)
                logger.info(f"binary_calc: {expression} = {result_str}")
                return {
                    "success": True,
                    "output": result_str,
                    "decimal": result,
                    "expression": expression,
                }

            # Just a number standing alone (identity)
            m = re.match(r'^(\d+)$', expression)
            if m:
                result_str = expression.lstrip("0") or "0"
                return {
                    "success": True,
                    "output": result_str,
                    "decimal": self._to_int(expression),
                    "expression": expression,
                }

            return {"success": False, "output": "", "error": f"Could not parse expression: {expression}"}
        except Exception as e:
            return {"success": False, "output": "", "error": f"Calculation error: {e}"}
