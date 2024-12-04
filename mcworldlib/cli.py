# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Command-line utility and related helper functions

Exported items:
    save_world -- Helper to conditionally save the world
"""

__all__ = [
    'basic_parser',
    'save_world'
]


import argparse
import logging

log = logging.getLogger(__name__)


def basic_parser(description=None,
                 player=True,
                 save=True,
                 default_world="New World",
                 default_player="Player",
                 **kw_argparser):
    parser = argparse.ArgumentParser(description=description, **kw_argparser)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quiet', '-q', dest='loglevel',
                       const=logging.WARNING, default=logging.INFO,
                       action="store_const",
                       help="Suppress informative messages.")
    group.add_argument('--verbose', '-v', dest='loglevel',
                       const=logging.DEBUG,
                       action="store_const",
                       help="Verbose mode, output extra info.")

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

    # Patch argparse so arguments have a suitable `name` property
    argparse.Action.name = property(
        lambda self: argparse.ArgumentError(self, "").argument_name
    )

    return parser


def save_world(world, save=False):
    """Conditionally saves the world. Convenience boilerplate"""
    if save:
        log.info("Applying changes and saving world...")
        world.save()
    else:
        log.warning("Not saving world, use --save to apply changes")
