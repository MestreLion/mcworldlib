# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Command-line utility and related helper functions.

Exported items:
    ArgumentParser -- argparse.ArgumentParser subclass with additional features
    basic_parser -- argparse-based parser with convenient options for Minecraft tools
    save_world -- Helper to conditionally save the world
"""

from __future__ import annotations

__all__ = [
    "ArgumentParser",
    "basic_parser",
    "save_world",
]

import argparse
import datetime
import logging
import typing as t

log = logging.getLogger(__name__)

# For basic_parser, used in ArgumentParser.epilog
COPYRIGHT = """
Copyright (C) {YEAR} Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>
"""

class ArgumentParser(argparse.ArgumentParser):
    __doc__ = (
        (argparse.ArgumentParser.__doc__ or "")
        + f"""
    Changed in {__name__}:"""
    """
    - description -- Only first non-blank line is considered, unless multiline
        is True. Convenient when using a module's __doc__ as description.
    - epilog -- If not empty, to respect line breaks formatter_class is set to
        argparse.RawDescriptionHelpFormatter, which also affects description.
    - suggest_on_error -- default to True instead of False.
    - Action objects returned by .add_argument() have a `name` property appropriate
        for using in error messages.
    - .error() accepts an optional `argument` option, if set to an Action object
        will format the error message appropriately for that argument, just like
        built-in parser errors do.
    New Arguments:
    - multiline -- If True, do not limit description to its first non-blank line
        and also set formatter_class to argparse.RawDescriptionHelpFormatter,
        which also affects epilog. (default: False)
    - loglevel_dest -- dest (name) of pre-created logging level parser
        argument, set as mutually-exclusive -q/--quiet|-v/--verbose options.
        If empty, no such options are created. (default: "loglevel")
    - debug_dest -- dest of the debug argument, a convenience bool attribute
        automatically created by parse_args() and set to True when the above
        loglevel is <logging.DEBUG> (i.e, when '-v/--verbose' is parsed).
        If empty, no such attribute is created. (default: "debug")
    - version -- if not empty, add '-V/--version' argument with `version` action
        and a "%(prog)s <version>" string. (default: None)
    """
    )

    def __init__(
        self,
        *args: t.Any,
        multiline: bool = False,
        loglevel_dest: str = "loglevel",
        debug_dest: str = "debug",
        version: str | None = None,
        **kwargs: t.Any,
    ):
        super().__init__(*args, **kwargs)

        if "suggest_on_error" not in kwargs:
            # New in Python 3.14
            self.suggest_on_error = True

        if self.description is not None and not multiline:
            self.description = self.description.strip().split("\n", maxsplit=1)[0]

        if multiline or self.epilog:
            self.formatter_class = argparse.RawDescriptionHelpFormatter

        self.loglevel_dest = loglevel_dest
        self.debug_dest = debug_dest

        if self.loglevel_dest:
            group = self.add_mutually_exclusive_group()
            group.add_argument(
                "-q",
                "--quiet",
                dest=self.loglevel_dest,
                const=logging.WARNING,
                default=logging.INFO,
                action="store_const",
                help="Suppress informative messages.",
            )
            group.add_argument(
                "-v",
                "--verbose",
                dest=self.loglevel_dest,
                const=logging.DEBUG,
                action="store_const",
                help="Verbose mode, output extra info.",
            )

        if version:
            self.add_argument(
                "-V",
                "--version",
                action="version",
                version=f"%(prog)s {version}",
            )

        # Patch argparse so arguments have a suitable `name` property
        argparse.Action.name = property(
            lambda self: argparse.ArgumentError(self, "").argument_name
        )

    def parse_args(  # type: ignore  # accurate typing requires overload
        self, *args: t.Any, log_args: bool = True, **kwargs: t.Any
    ) -> argparse.Namespace:
        arguments: argparse.Namespace = super().parse_args(*args, **kwargs)
        if self.debug_dest and self.loglevel_dest:
            setattr(
                arguments,
                self.debug_dest,
                getattr(arguments, self.loglevel_dest) == logging.DEBUG,
            )
            if log_args:
                logging.basicConfig(
                    level=getattr(arguments, self.loglevel_dest),
                    format="%(levelname)s: %(message)s",
                    # format="[%(asctime)s %(funcName)s %(levelname)s] %(message)s",
                    # datefmt="%Y-%m-%d %H:%M:%S",
                )
                log.debug("Arguments: %s", arguments)
        return arguments

    def error(self, message:str, argument: argparse.Action | None = None):
        if argument is None:
            super().error(message)
        else:
            super().error(str(argparse.ArgumentError(argument, message)))


def basic_parser(description=None, *,
                 world=True,
                 player=True,
                 save=True,
                 copyright: int | bool = False,
                 default_world="New World",
                 default_player="Player",
                 **kw_argparser):
    """Basic argparse-based parser with convenient options for Minecraft tools."""

    if copyright:
        year = datetime.datetime.now().year if isinstance(copyright, bool) else copyright
        epilogs = [COPYRIGHT.format(YEAR=year).strip()]
        if epilog := kw_argparser.get("epilog", "").strip():
            epilogs.insert(0, epilog)
        kw_argparser["epilog"] = "\n\n".join(epilogs)

    parser = ArgumentParser(description=description, **kw_argparser)

    if world:
        parser.add_argument('--world', '-w', default=default_world,
                            help="Minecraft world, either its 'level.dat' file"
                                 " or a name under '~/.minecraft/saves' folder."
                                 " [Default: '%(default)s']")
    if player:
        parser.add_argument('--player', '-p', default=default_player,
                            help="Player name."
                                 " [Default: '%(default)s']")
    if save:
        parser.add_argument('--save', '-S',
                            default=False, action="store_true",
                            help="Apply changes and save the world.")
    return parser


def save_world(world, save=False):
    """Conditionally saves the world. Convenience boilerplate"""
    if save:
        log.info("Applying changes and saving world...")
        world.save()
    else:
        log.warning("Not saving world, use --save to apply changes")
