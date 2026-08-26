-- Demo-only seed data. Password hashes are placeholders; replace through the app or a seed script before use.
insert into "User" ("id", "login", "displayName", "passwordHash", "role", "isActive", "mustChangePassword", "createdAt", "updatedAt")
values
  ('00000000-0000-0000-0000-000000000001', 'admin', 'Администратор', 'replace-with-scrypt-hash', 'ADMIN', true, true, now(), now()),
  ('00000000-0000-0000-0000-000000000101', 'kitasov', 'Китасов Саша', 'replace-with-scrypt-hash', 'CUTTER', true, true, now(), now())
on conflict ("login") do nothing;

insert into "CutterProfile" ("id", "userId", "displayName", "sourceSheet", "isActive", "createdAt", "updatedAt")
values
  ('10000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000101', 'Китасов Саша', 'Китасов Саша', true, now(), now())
on conflict ("userId") do nothing;
