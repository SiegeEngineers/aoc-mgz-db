"""CLI for MGZ database."""
import argparse
import json
import logging
import os

import coloredlogs
import tqdm
from mgzdb.api import API
from mgzdb.util import parse_series_path


CMD_QUERY = 'query'
CMD_ADD = 'add'
CMD_REMOVE = 'remove'
CMD_GET = 'get'
CMD_RESET = 'reset'
CMD_BOOTSTRAP = 'bootstrap'
SUBCMD_FILE = 'file'
SUBCMD_MATCH = 'match'
SUBCMD_SERIES = 'series'
SUBCMD_SUMMARY = 'summary'
SUBCMD_ARCHIVE = 'archive'
SUBCMD_DB = 'db'
DEFAULT_DB = 'sqlite:///data.db'


def main(args): # pylint: disable=too-many-branches
    """Handle arguments."""

    add_callback = None
    if args.progress:
        progress = tqdm.tqdm(unit='mgz')
        coloredlogs.set_level('CRITICAL')
        add_callback = progress.update

    db_api = API(
        args.database, args.store_path,
        voobly_key=args.voobly_key,
        voobly_username=args.voobly_username,
        voobly_password=args.voobly_password,
        consecutive=args.consecutive,
        callback=add_callback
    )

    # Add
    if args.cmd == CMD_ADD:

        db_api.start()

        # File
        if args.subcmd == SUBCMD_FILE:
            for rec in args.rec_path:
                db_api.add_file(rec, args.source, None)
                if args.progress:
                    progress.total = db_api.total

        # Match
        elif args.subcmd == SUBCMD_MATCH:
            for url in args.url:
                db_api.add_match(args.platform, url)
                if args.progress:
                    progress.total = db_api.total

        # Series
        elif args.subcmd == SUBCMD_SERIES:
            for path in args.zip_path:
                series, series_id = parse_series_path(path)
                db_api.add_series(
                    path, series, series_id
                )
                if args.progress:
                    progress.total = db_api.total

        # Database
        elif args.subcmd == SUBCMD_DB:
            remote_api = API(args.remote_db_url, args.remote_store_path)
            db_api.add_db(remote_api)
            if args.progress:
                progress.total = db_api.total

        # Archive
        elif args.subcmd == SUBCMD_ARCHIVE:
            db_api.add_archive(args.archive_path)
            if args.progress:
                progress.total = db_api.total

        db_api.finished()
        if args.progress:
            progress.close()

    # Remove
    elif args.cmd == CMD_REMOVE:
        db_api.remove(file_id=args.file, match_id=args.match)

    # Query
    elif args.cmd == CMD_QUERY:
        print(json.dumps(db_api.query(args.subcmd, **vars(args)), indent=2))

    # Get
    elif args.cmd == CMD_GET:
        filename, data = db_api.get(args.file)
        output_filename = args.output_path or filename
        if os.path.exists(output_filename):
            print('file already exists:', output_filename)
            return
        with open(output_filename, 'wb') as handle:
            handle.write(data)
        print(output_filename)

    # Reset
    elif args.cmd == CMD_RESET:
        if input('reset database completely? [y/N] ') == 'y':
            db_api.reset()


def setup():
    """Setup CLI."""
    coloredlogs.install(
        level='INFO',
        fmt='%(asctime)s [%(process)d]%(name)s %(levelname)s %(message)s'
    )
    logging.getLogger('paramiko').setLevel(logging.WARN)
    logging.getLogger('voobly').setLevel(logging.WARN)
    logging.getLogger('sqlalchemy').setLevel(logging.INFO)

    parser = argparse.ArgumentParser()
    default_file_path = os.path.abspath('.')

    # Global options
    parser.add_argument('-d', '--database', default=os.environ.get('MGZ_DB', DEFAULT_DB))
    parser.add_argument('-sp', '--store-path', default=os.environ.get('MGZ_STORE_PATH', default_file_path))
    parser.add_argument('-vk', '--voobly-key', default=os.environ.get('VOOBLY_KEY', None))
    parser.add_argument('-vu', '--voobly-username', default=os.environ.get('VOOBLY_USERNAME', None))
    parser.add_argument('-vp', '--voobly-password', default=os.environ.get('VOOBLY_PASSWORD', None))
    parser.add_argument('-c', '--consecutive', action='store_true', default=False)
    parser.add_argument('-p', '--progress', action='store_true', default=False)

    # Commands
    subparsers = parser.add_subparsers(dest='cmd')
    subparsers.required = True

    # "query" command
    query = subparsers.add_parser(CMD_QUERY)

    # "query" subcommands
    query_subparsers = query.add_subparsers(dest='subcmd')
    query_subparsers.required = True

    # "query match"
    query_match = query_subparsers.add_parser(SUBCMD_MATCH)
    query_match.add_argument('match_id', type=int)

    # "query file"
    query_file = query_subparsers.add_parser(SUBCMD_FILE)
    query_file.add_argument('file_id', type=int)

    # "query series"
    query_series = query_subparsers.add_parser(SUBCMD_SERIES)
    query_series.add_argument('series_id', type=int)

    # "query summary"
    query_subparsers.add_parser(SUBCMD_SUMMARY)

    # "add" command
    add = subparsers.add_parser(CMD_ADD)

    # "add" subcommands
    add_subparsers = add.add_subparsers(dest='subcmd')
    add_subparsers.required = True

    # "add file"
    add_file = add_subparsers.add_parser(SUBCMD_FILE)
    add_file.add_argument('-s', '--source', default='cli')
    add_file.add_argument('--series')
    add_file.add_argument('--tournament')
    add_file.add_argument('rec_path', nargs='+')

    # "add match"
    add_match = add_subparsers.add_parser(SUBCMD_MATCH)
    add_match.add_argument('platform')
    add_match.add_argument('url', nargs='+')

    # "add series"
    add_series = add_subparsers.add_parser(SUBCMD_SERIES)
    add_series.add_argument('zip_path', nargs='+')

    # "add database"
    add_db = add_subparsers.add_parser(SUBCMD_DB)
    add_db.add_argument('remote_db_url')
    add_db.add_argument('remote_store_path')

    # "add archive"
    add_archive = add_subparsers.add_parser(SUBCMD_ARCHIVE)
    add_archive.add_argument('archive_path')

    # "remove" command
    remove = subparsers.add_parser(CMD_REMOVE)
    remove_group = remove.add_mutually_exclusive_group(required=True)
    remove_group.add_argument('-f', '--file')
    remove_group.add_argument('-m', '--match')

    # "get" command
    get = subparsers.add_parser(CMD_GET)
    get.add_argument('file')
    get.add_argument('-o', '--output-path')

    # "reset" command
    subparsers.add_parser(CMD_RESET)

    # "bootstrap" command
    subparsers.add_parser(CMD_BOOTSTRAP)

    args = parser.parse_args()
    main(args)


if __name__ == '__main__':
    setup()
