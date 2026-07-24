# standpoint skill

This folder packages `standpoint` as a **skill** for Claude / OpenCode (and any host
that reads the [Agent Skills](https://agentskills.io) format). The skill teaches the
agent when to turn a comparison table into a positioning map, and how to drive the tool
across its surfaces.

```
skills/standpoint/
├── SKILL.md                       # frontmatter (name + description = the trigger) + instructions
├── references/
│   ├── interfaces.md              # library / CLI / GUI / API / MCP / Docker / conda
│   └── input-and-output.md        # table rules and the files written
└── scripts/
    └── positioning_summary.py     # table -> figure (SVG + PNG) + analysis, then print the paths
```

The agent reads `SKILL.md` first; it pulls a `references/*.md` file only when it needs
that depth (progressive disclosure), so the always-loaded part stays small.

## Install it

Point your agent's skills directory at this folder (symlink so it tracks the repo):

```bash
# Claude
ln -s "$(pwd)/skills/standpoint" ~/.claude/skills/standpoint
# OpenCode
ln -s "$(pwd)/skills/standpoint" ~/.opencode/skills/standpoint
```

Then the agent invokes it whenever a request matches the triggers — catalogued
exhaustively in [TRIGGERS.md](../TRIGGERS.md) at the repository root.
