STATEMENTS = [
    """
    create table if not exists public.ingest_jobs (
      id uuid primary key,
      user_id uuid not null,
      publication text not null,
      district_id text not null,
      district_name text not null,
      prakhand_id text not null,
      prakhand_name text not null,
      body_type text not null,
      body_id text not null,
      body_name text not null,
      body_key text not null,
      status text not null,
      error text,
      expected_urls text not null default '[]',
      created_at timestamptz not null default now()
    )
    """,
    """
    create table if not exists public.source_files (
      id uuid primary key,
      job_id uuid not null,
      source_url text not null unique,
      ward_no integer,
      content_hash text,
      s3_uri text,
      page_count integer,
      status text not null,
      error text,
      created_at timestamptz not null default now()
    )
    """,
    """
    create table if not exists public.source_pages (
      file_id uuid not null references public.source_files(id) on delete cascade,
      page_no integer not null,
      status text not null,
      voter_count integer not null default 0,
      error text,
      primary key (file_id, page_no)
    )
    """,
    """
    create table if not exists public.downloaded_bodies (
      body_key text primary key,
      job_id uuid not null,
      downloaded_at timestamptz not null default now()
    )
    """,
    "create index if not exists source_files_job_idx on public.source_files (job_id)",
    "alter table public.ingest_jobs enable row level security",
    "alter table public.source_files enable row level security",
    "alter table public.source_pages enable row level security",
    "alter table public.downloaded_bodies enable row level security",
]
