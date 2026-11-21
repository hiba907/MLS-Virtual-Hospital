-- feedback_survey.sql  -  anonymous feedback for the MLS Virtual Hospital (students + professors/clinicians)
-- Run ONCE in Supabase -> SQL Editor -> New query -> paste ALL -> Run.
-- (If the editor adds a lone ")" at the very end, delete it before pressing Run.)
--
-- Privacy design:
--   * vh_fb_responses holds ANSWERS ONLY. No name, no email, no account id, no time of day, no running number
--     (the id is a random uuid), so an answer cannot be traced back to a person.
--   * vh_fb_tokens holds a scrambled one-way code (HMAC) of the account, only to stop duplicate responses.
--     It has no timestamp and no link to a response row.
--   * Row Level Security is on for both tables; the app uses the service_role key from Streamlit Secrets,
--     so the public (anon) key can read nothing here.

create table if not exists vh_fb_responses (
  id            uuid primary key default gen_random_uuid(),
  submitted_on  date        not null default current_date,        -- date only
  kind          text        not null check (kind in ('student','faculty')),
  year_level    text,
  specialty     text,
  q_overall     smallint    check (q_overall   between 1 and 5),
  q_reasoning   smallint    check (q_reasoning between 1 and 5),
  q_realism     smallint    check (q_realism   between 1 and 5),
  q_usability   smallint    check (q_usability between 1 and 5),
  q_ai          smallint    check (q_ai        between 1 and 5),
  would_recommend text      check (would_recommend in ('Yes','Maybe','No')),
  liked         text,
  disliked      text,
  suggestions   text,
  extra         jsonb       not null default '{}'::jsonb          -- extra items (professor form, usage, access before)
);

create table if not exists vh_fb_tokens (
  token  text primary key,                                         -- one-way code; one response per account per survey
  kind   text not null
);

create index if not exists vh_fb_responses_kind on vh_fb_responses(kind);

alter table vh_fb_responses enable row level security;
alter table vh_fb_tokens    enable row level security;
