create table
  public.global_inventory (
    id bigint generated by default as identity,
    created_at timestamp with time zone not null default (now() at time zone 'pst'::text),
    num_potions integer not null,
    num_red_ml integer not null,
    gold integer not null,
    num_green_ml integer not null,
    num_blue_ml integer not null,
    num_dark_ml integer not null,
    constraint global_inventory_pkey primary key (id)
  ) tablespace pg_default;

create table
  public.potions (
    id bigint generated by default as identity,
    sku text not null,
    name text null,
    price integer not null default 50,
    red integer not null default 0,
    green integer not null default 0,
    blue integer not null default 0,
    dark integer not null default 0,
    quantity integer not null default 0,
    constraint potions_pkey primary key (id),
    constraint potions_sku_key unique (sku)
  ) tablespace pg_default;

create table
  public.shopping_carts (
    id bigint generated by default as identity,
    created_at timestamp with time zone not null default (now() at time zone 'pst'::text),
    customer text not null,
    constraint shopping_carts_pkey primary key (id)
  ) tablespace pg_default;

create table
  public.cart_contents (
    id bigint generated by default as identity,
    created_at timestamp with time zone not null default (now() at time zone 'pst'::text),
    cart_id bigint not null,
    potion_sku text not null,
    quantity_requested integer not null,
    constraint cart_contents_pkey primary key (id),
    constraint cart_contents_cart_id_fkey foreign key (cart_id) references shopping_carts (id) on update cascade on delete cascade,
    constraint cart_contents_potion_sku_fkey foreign key (potion_sku) references potions (sku) on update cascade
  ) tablespace pg_default;

create table
  public.transactions (
    id bigint generated by default as identity,
    created_at timestamp with time zone not null default (now() at time zone 'pst'::text),
    cart_id bigint not null,
    success boolean not null,
    payment text not null,
    gold_paid integer not null,
    constraint transactions_pkey primary key (id),
    constraint transactions_cart_id_key unique (cart_id),
    constraint transactions_cart_id_fkey foreign key (cart_id) references shopping_carts (id) on update cascade on delete cascade
  ) tablespace pg_default;