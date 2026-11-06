-- Research Hub tables. Run once in Supabase SQL Editor. Safe to run again.
create table if not exists vh_research_projects (
  id bigint generated always as identity primary key,
  title text not null, question text, field text, study_type text, background text,
  seeking text, stage text default 'Idea', status text default 'pending',
  owner_id text, owner_name text, ethics_status text, ethics_note text,
  mentor_name text, moderator_note text, created_at timestamp default now()
);
create table if not exists vh_research_members (
  id bigint generated always as identity primary key,
  project_id bigint, user_id text, name text, role text, status text, message text,
  created_at timestamp default now()
);
create table if not exists vh_research_refs (
  id bigint generated always as identity primary key,
  project_id bigint, pmid text, title text, citation text, doi text, added_by text,
  created_at timestamp default now()
);
create table if not exists vh_research_updates (
  id bigint generated always as identity primary key,
  project_id bigint, author text, text text, created_at timestamp default now()
);
-- RLS ON: the app uses the private service key, which bypasses it; the public anon key gets no access
alter table vh_research_projects enable row level security;
alter table vh_research_members  enable row level security;
alter table vh_research_refs     enable row level security;
alter table vh_research_updates  enable row level security;
