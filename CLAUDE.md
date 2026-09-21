# CLAUDE.md
@AGENTS.md

## Específico do Claude Code
- Use **plan mode** para tarefas que tocam mais de um módulo.
- Use subagentes para exploração ampla (buscar no código, ler notebooks grandes) e mantenha o contexto principal limpo.
- Permissões do agente estão em `.claude/settings.json` (menor privilégio). Não peça para contorná-las; proponha mudança via ADR.
- Ao terminar uma sessão longa, resuma progresso e próximos passos em `specs/DECISIONS.md` (seção "Log de sessão") se houver decisão tomada.
