-- Case Discussion Rooms tables. Run once in Supabase SQL Editor. Safe to run again.
create table if not exists vh_disc_threads (
  id bigint generated always as identity primary key,
  title text not null, body text, department text, case_ref text,
  author_id text, author_name text, status text default 'open',
  pinned boolean default false, hidden boolean default false,
  images jsonb default '[]'::jsonb,
  last_activity text, created_at timestamp default now()
);
create table if not exists vh_disc_posts (
  id bigint generated always as identity primary key,
  thread_id bigint, author_id text, author_name text, body text,
  images jsonb default '[]'::jsonb, is_faculty boolean default false,
  helpful_by jsonb default '[]'::jsonb, best boolean default false, hidden boolean default false,
  created_at timestamp default now()
);
create table if not exists vh_disc_follows (
  id bigint generated always as identity primary key,
  thread_id bigint, user_id text, email text, last_emailed text,
  created_at timestamp default now()
);
create table if not exists vh_disc_prefs (
  id bigint generated always as identity primary key,
  user_id text unique, email text, email_mode text default 'instant', last_seen text,
  created_at timestamp default now()
);
alter table vh_disc_threads disable row level security;
alter table vh_disc_posts   disable row level security;
alter table vh_disc_follows disable row level security;
alter table vh_disc_prefs   disable row level security;
