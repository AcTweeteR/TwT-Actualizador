"""Prepare a reversible two-store XStream watched restore.

Stages files in an isolated directory. Never changes active Kodi files.
"""
import json
import os
from pathlib import Path
from .trakt_projection import project_watched
from .trakt_resume_bridge import existing_playback_references, stage_resume


def stage_restore(plan, *, profile, account, movie_source, episode_source, staging_directory):
    staging = Path(staging_directory)
    if staging.is_symlink() or not staging.is_dir():
        raise ValueError('unsafe staging directory')
    movie = staging / 'watched_movies.json'
    episode = staging / 'watched_episodes.json'
    if movie.exists() or episode.exists():
        raise FileExistsError('staging output already exists')
    sources = (Path(movie_source), Path(episode_source))
    for source in sources:
        if source.is_symlink() or (source.exists() and not source.is_file()):
            raise ValueError('source must be a regular file when present')
    for source, target in zip(sources, (movie, episode)):
        data = json.loads(source.read_text('utf-8')) if source.exists() else {}
        if not isinstance(data, dict):
            raise ValueError('invalid watched store')
        with target.open('x', encoding='utf-8') as output:
            json.dump(data, output, ensure_ascii=False)
    counts = {}
    for kind in ('movie', 'episode'):
        subset = dict(plan, items=[x for x in plan['items'] if x['identity']['kind'] == kind])
        counts[kind] = project_watched(subset, profile=profile, account=account,
                                       movie_path=movie, episode_path=episode, dry_run=False)
    return {'movie_path': str(movie), 'episode_path': str(episode),
            'movies': counts['movie']['movies'], 'episodes': counts['episode']['episodes'],
            'active_kodi_writes': 0}


def stage_complete_restore(plan, *, profile, account, xstream_profile,
                           movie_source, episode_source, staging_directory):
    """Stage watched and exact-reference resume data without touching active stores."""
    staging = Path(staging_directory)
    watched = stage_restore(plan, profile=profile, account=account,
        movie_source=movie_source, episode_source=episode_source,
        staging_directory=staging)
    try:
        references, current_resume = existing_playback_references(
            xstream_profile, profile, plan['items'])
        resume = stage_resume(plan, references, current_resume)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return dict(watched, resume_path=None, resumes_added=0, resumes_updated=0,
                    resumes_deferred=0, resume_error=True)
    resume_path = staging / 'resume_points.json'
    with resume_path.open('x', encoding='utf-8') as output:
        os.chmod(resume_path, 0o600)
        json.dump(resume['staged'], output, ensure_ascii=False)
        output.flush()
        os.fsync(output.fileno())
    return dict(watched, resume_path=str(resume_path),
        resumes_added=resume['added'], resumes_updated=resume['updated'],
        resumes_deferred=len(resume['deferred']), resume_error=False)
