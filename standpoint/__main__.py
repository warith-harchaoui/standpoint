"""Module entry point so ``python -m standpoint`` runs the argparse CLI.

This is the same command the ``standpoint`` console script installs; it lets the
tool run without a console script on the PATH (e.g. inside a container, or right
after a plain ``pip install`` in an environment whose scripts dir is not active).
It only forwards to ``standpoint.main``; all parsing and work live there.
"""

from standpoint import main

if __name__ == "__main__":
    main()
