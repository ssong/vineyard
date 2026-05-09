"""Stack profiles — pluggable language/framework targets."""

from vineyard.stacks.backend.profile import BACKEND
from vineyard.stacks.base import StackProfile, StackRegistry, registry
from vineyard.stacks.cli.profile import CLI
from vineyard.stacks.django.profile import DJANGO
from vineyard.stacks.fastapi.profile import FASTAPI
from vineyard.stacks.nextjs.profile import NEXTJS
from vineyard.stacks.rails.profile import RAILS
from vineyard.stacks.tui.profile import TUI

for _profile in (NEXTJS, RAILS, FASTAPI, DJANGO, BACKEND, CLI, TUI):
    registry.register(_profile)

__all__ = ["StackProfile", "StackRegistry", "registry"]
