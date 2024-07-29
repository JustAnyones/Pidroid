import sys
import os

from pathlib import Path

sys.path.append(os.path.join(str(Path(__file__).parents[1]), "pidroid"))

import pidroid # pyright: ignore[reportUnusedImport] # Loads the environment that's required for testing
