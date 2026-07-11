import os
import shutil
from pathlib import Path

# Setup paths
root_dir = Path(r"d:\Project\SciParser")
skills_dir = root_dir / ".agents" / "skills"
wiki_dir = root_dir / "llm_wiki"

# Create llm_wiki
wiki_dir.mkdir(exist_ok=True)

# Process all skills
skill_names = []
for item in skills_dir.iterdir():
    if item.is_dir() and (item / "SKILL.md").exists():
        skill_name = item.name
        skill_names.append(skill_name)
        
        # Read the original SKILL.md
        content = (item / "SKILL.md").read_text(encoding="utf-8")
        
        # Write to llm_wiki/<skill_name>.md
        flat_file = wiki_dir / f"{skill_name}.md"
        flat_file.write_text(content, encoding="utf-8")
        print(f"Migrated {skill_name} -> llm_wiki/{skill_name}.md")

# Create master skill sciparser-wiki
master_skill_dir = skills_dir / "sciparser-wiki"
master_skill_dir.mkdir(exist_ok=True)

master_content = f"""---
name: sciparser-wiki
description: Comprehensive knowledge base for SciParser. Use this skill to learn about stealth, architecture, booking, extraction, planning, and other core systems.
---
# SciParser Knowledge Base (llm_wiki)

All the specialized instructions, procedures, and architectural knowledge have been consolidated into a flat knowledge base in the `llm_wiki/` directory at the project root.

When you need to understand how to handle a specific domain, use the `view_file` tool to read the appropriate file from `d:\\Project\\SciParser\\llm_wiki\\`.

## Available Knowledge Modules:

"""

for sn in sorted(skill_names):
    master_content += f"- **{sn}**: `d:\\Project\\SciParser\\llm_wiki\\{sn}.md`\n"

master_content += """
**INSTRUCTION**: Use the `view_file` tool to read the relevant flat `.md` file from `llm_wiki/` whenever you need specialized knowledge for a task.
"""

(master_skill_dir / "SKILL.md").write_text(master_content, encoding="utf-8")
print(f"Created master skill at {master_skill_dir / 'SKILL.md'}")

# Delete old skill folders
for sn in skill_names:
    old_dir = skills_dir / sn
    if old_dir.exists():
        shutil.rmtree(old_dir)
        print(f"Deleted old nested folder: {old_dir}")

print("\nMigration complete! The knowledge base has been flattened into llm_wiki/")
