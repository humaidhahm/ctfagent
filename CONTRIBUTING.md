# Contributing to CTFAgent

Contributions are welcome and appreciated!

## Ways to Contribute

### Report Bugs

- Open a [GitHub Issue](https://github.com/humaidhahm/ctfagent/issues/new?template=bug.yml)
- Include: description, reproduction steps, expected vs actual behavior
- Include environment details (Python version, OS, tool versions)

### Suggest Features

- Open a [Feature Request](https://github.com/humaidhahm/ctfagent/issues/new?template=feature.yml)
- Describe the feature, use case, and how it fits the project

### Add Tools

1. Create a new tool in `backend/tools/<domain>/`
2. Extend `BaseTool` from `backend/tools/base.py`
3. Register it in `backend/agents/tool_registry.py`
4. Add to the agent's `AVAILABLE_TOOLS` list

### Improve Agents

- Domain agents live in `backend/agents/`
- Update system prompts for better LLM performance
- Add new tool integrations
- Improve error handling and retry logic

## Development Setup

```bash
git clone https://github.com/humaidhahm/ctfagent.git
cd ctfagent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Code Style

- Follow PEP 8
- Use type hints
- Write async functions for tool execution
- Add docstrings for public methods
- Keep tools focused on a single responsibility

## Testing

```bash
pytest tests/
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Code of Conduct

Be respectful, inclusive, and constructive. Harassment and trolling are not tolerated.
