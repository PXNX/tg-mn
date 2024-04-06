drop table posts;

create table posts
(
    post_id        int not null,
    lang           char(2) not null,
    msg_id         int     not null,
    media_group_id varchar(120),
    reply_id       int,
    file_type      int,
    file_id        varchar(120),
    text           text,
    primary key (msg_id, lang)
);