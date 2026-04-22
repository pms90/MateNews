from __future__ import annotations

import argparse
from pathlib import Path

from .domain.models import RunConfig
from .pipeline.runner import build_site, fetch_source_batches
from .publish import PublishError, publish_site
from .sources.registry import get_source_definitions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MateNews static site generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_sources_parser = subparsers.add_parser("list-sources", help="Show configured sources")
    list_sources_parser.set_defaults(handler=handle_list_sources)

    build_parser_obj = subparsers.add_parser("build", help="Fetch sources and build the local site")
    build_parser_obj.add_argument("--output-dir", default="site", help="Directory where the static site is written")
    build_parser_obj.add_argument(
        "--site-url",
        default="https://matenews.github.io/MateNews",
        help="Public base URL used in absolute links such as prev",
    )
    build_parser_obj.add_argument(
        "--sources",
        nargs="*",
        default=None,
        help="Optional list of source slugs to build",
    )
    build_parser_obj.add_argument(
        "--all-sources",
        action="store_true",
        help="Ignore the daily schedule and fetch every enabled source",
    )
    build_parser_obj.set_defaults(handler=handle_build)

    publish_parser = subparsers.add_parser("publish", help="Publish an already generated site")
    publish_parser.add_argument("--source-dir", default="site", help="Directory containing the generated static site")
    publish_parser.add_argument(
        "--target-dir",
        default="docs",
        help="Directory inside the Git repository that will be synchronized and published",
    )
    publish_parser.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository root or any directory inside it",
    )
    publish_parser.add_argument(
        "--message",
        default=None,
        help="Optional Git commit message for the publication commit",
    )
    publish_parser.add_argument("--remote", default="origin", help="Git remote used for push")
    publish_parser.add_argument("--branch", default=None, help="Optional Git branch used for push")
    publish_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Create the publication commit but do not push it",
    )
    publish_parser.set_defaults(handler=handle_publish)

    return parser


def handle_list_sources(args: argparse.Namespace) -> int:
    for definition in get_source_definitions():
        status = "implemented" if definition.is_implemented else "placeholder"
        enabled = "enabled" if definition.config.enabled else "disabled"
        print(f"{definition.config.slug}: {definition.config.name} [{status}, {enabled}]")
    return 0


def handle_build(args: argparse.Namespace) -> int:
    selected_slugs = set(args.sources) if args.sources else None
    config = RunConfig(output_dir=Path(args.output_dir), site_url=args.site_url)
    batches = fetch_source_batches(selected_slugs=selected_slugs, ignore_schedule=args.all_sources)
    build_site(batches, config=config)
    article_count = sum(len(batch.articles) for batch in batches)
    print(f"Generated {article_count} articles across {len(batches)} sources in {config.output_dir}")
    return 0


def handle_publish(args: argparse.Namespace) -> int:
    try:
        synchronized_files, commit_message = publish_site(
            source_dir=Path(args.source_dir),
            target_dir=Path(args.target_dir),
            repo_dir=Path(args.repo_dir),
            commit_message=args.message,
            remote=args.remote,
            branch=args.branch,
            push=not args.no_push,
        )
    except PublishError as exc:
        print(str(exc))
        return 1

    print(f"Published {synchronized_files} files from {args.source_dir} into {args.target_dir}")
    if commit_message is None:
        print("No Git changes detected after synchronization.")
    elif args.no_push:
        print(f"Created commit: {commit_message}")
    else:
        print(f"Created and pushed commit: {commit_message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())