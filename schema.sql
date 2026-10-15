create table if not exists chat_messages (
  id bigint generated always as identity primary key,
  user_id bigint not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists chat_messages_user_idx
  on chat_messages (user_id, id desc);

alter table chat_messages enable row level security;