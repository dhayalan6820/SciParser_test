import os
import shutil
from pathlib import Path

# Paths to delete
root_dir = Path(r"d:\Project\SciParser")
backend_src = root_dir / "Backend" / "src"
services_dir = backend_src / "services"
agents_dir = backend_src / "agents"
skills_dir = root_dir / ".agents" / "skills"

files_to_delete = [
    services_dir / "ATAG.py",
    services_dir / "memory_service.py",
    services_dir / "address_agent.py",
    services_dir / "booking_agent.py",
    services_dir / "calendar_agent.py",
    services_dir / "login_agent.py",
    services_dir / "aggregator_agent.py",
    services_dir / "deep_agent.py",
    services_dir / "obstacle_handler.py",
    services_dir / "recovery.py",
    services_dir / "observer.py",
    services_dir / "verifier.py",
    agents_dir / "specs" / "aggregator.agent.md",
    agents_dir / "specs" / "address.agent.md",
    agents_dir / "specs" / "calendar.agent.md",
    agents_dir / "specs" / "login.agent.md",
    agents_dir / "specs" / "booking.agent.md",
    agents_dir / "specs" / "recovery.md",
    agents_dir / "specs" / "planner.agent.md",
    agents_dir / "specs" / "coder.agent.md",
    agents_dir / "specs" / "browser.agent.md",
    agents_dir / "spec_loader.py"
]

for f in files_to_delete:
    if f.exists():
        os.remove(f)
        print(f"Deleted {f}")
    else:
        print(f"Did not find {f}")

# Delete skills directory if it exists
if skills_dir.exists():
    shutil.rmtree(skills_dir)
    print(f"Deleted {skills_dir}")

print("Architecture cleanup complete.")
