# Todo Workspace – Backend Task List (আপনার আসল কোড দেখে তৈরি)

> এই ভার্সন `todo-api-main.zip` এর সোর্স কোড পড়ে বানানো। আগের ⚠️ অনুমানগুলো এখন যাচাই করা হয়েছে।
> প্রজেক্টের apps: `accounts`, `todos`, `categories`, `core`, `config`। tests: `tests/unit`, `tests/integration` (মোট ~৫৬টি test)।

---

## ১. কোড পড়ে যা নিশ্চিত হলাম

| বিষয় | বর্তমান অবস্থা | নতুন কাজে প্রভাব |
|---|---|---|
| `accounts/models.py` | `AbstractUser` থেকে `username/first_name/last_name` বাদ; `name`, `email` (case-insensitive unique)। **`role` নেই** | `role` যোগ করতে হবে; `create_superuser` এ `role=admin` default দিতে হবে |
| `Todo.user` | `FK(User, CASCADE, related_name="todos", db_index=False)` | `assigner` এ রূপান্তর; **৫টি index সবই `user` দিয়ে শুরু** → নতুন করে সাজাতে হবে |
| `Todo.is_completed` | Boolean; filter `?status=completed\|pending` এটার ওপর | নতুন `status` (pending/in_progress/completed) এর সাথে নাম-সংঘাত |
| `todos/views.py` | `get_queryset()` = `filter(user=request.user)`; `perform_create` এ `user=request.user`; কমেন্টে লেখা "Admins get no exception" | Scope বদলাতে হবে; admin-র জন্য আলাদা read-only endpoint লাগবে (বোনাস) |
| `todos/serializers.py` | `update()` এ `Todo.objects.filter(pk=..., user_id=instance.user_id).update(...)` (পুরো ownership এই লাইনে hardcoded) | `user_id` filter বদলাতে হবে, নইলে assignee এর update ০ row আপডেট করে 404 দেবে |
| `categories/permissions.py` | `DjangoModelPermissions` + `is_staff` | `role` থেকে আলাদা; সিদ্ধান্ত দরকার (নিচে ৩ নং) |
| Login/Register response | `user_payload()` শুধু `id, name, email` | `role`, `team` যোগ করতে হবে |
| Throttle | `user: 100/min` (সব endpoint মিলিয়ে, প্রতি user) | Notification polling এই budget খেয়ে ফেলবে |
| JWT | access ১৫ মিনিট, `SafeJWTAuthentication` প্রতি request এ DB থেকে user লোড করে | ✅ Role বদলালে **সাথে সাথে** কার্যকর হবে (token এ role নেই), ভালো |
| Error handler | `core/exceptions.py`: 403/404/409 সব `{"error","code"}` format এ; `IntegrityError` → 409 | ✅ নতুন error গুলো একই format এ পাবেন |
| `RegisterSerializer` | শুধু `name,email,password` নেয়; বাকি সব ignore | ✅ Register দিয়ে `role=admin` ঢোকানো যাবে না (model default `member` রাখলেই হবে) |
| Strict fields | `core/fields.py` এ `StrictPrimaryKeyRelatedField`, `StrictIntegerChoiceField` ইত্যাদি | ✅ `assignee_id`, `role`, `team_id` validation এ পুনর্ব্যবহার করুন |
| Repo hygiene | `requirements.txt` ও `requriements.txt` (বানান ভুল, পুরোনো কপি) দুটোই আছে | `requriements.txt` মুছে ফেলুন |

---

## ২. মূল পরিবর্তনের সারসংক্ষেপ

1. নতুন model: `Team`, `Membership`, `Notification`; `User.role`
2. `Todo`: `user` → `assigner`, নতুন `assignee`, `team`, `status`, `assignment_status`
3. Permission: owner-সব-পারে → assignee edit করবে, assigner শুধু দেখবে
4. নতুন API: `/auth/me`, teams, admin users, assign/accept/reject, notifications
5. Bonus: admin dashboard + read-only monitoring API

প্রস্তাবিত নতুন Django app: `teams`, `notifications`, (বোনাসে) `dashboard`। Admin user API `accounts` এ রাখুন।

---

## ৩. আগে যে সিদ্ধান্তগুলো নিতে হবে (README তে "Decisions" এ লিখবেন)

- [ ] **Category permission:** এখন `is_staff` + Django model permission। `role=admin` আলাদা। **সুপারিশ:** Category কোড **না ছুঁয়ে** রাখুন (ঝুঁকি কম, `test_permissions.py` ভাঙবে না), আর README তে লিখুন "category management = Django staff, workspace admin = role"। চাইলে পরে `role=admin` কে category-তেও অনুমতি দিতে পারেন।
- [ ] **`is_completed` কী হবে:** Assignment এ todo status = `pending / in_progress / completed`। **সুপারিশ:** `status` field আনুন, data migration এ `is_completed=True → completed`, `False → pending`; `is_completed` কলাম সরিয়ে response এ read-only derived field হিসেবে রাখুন। এতে দুই জায়গায় সত্য থাকে না।
- [ ] **Existing `?status=` filter:** এখন `completed|pending`। নতুন `status` (৩ মান) ও `assignment_status` (pending/accepted/rejected) এর সাথে গুলিয়ে যাবে। **সুপারিশ:** `?status=` ৩ মানই নিক; assignment এর জন্য `?assignment_status=`।
- [ ] **Unassigned todo:** `assignee=null` হলে কে edit করবে? **সুপারিশ:** assign করার আগে creator (assigner) edit/delete করতে পারবে; assign হওয়ার পর শুধু assignee edit করবে।
- [ ] **নিজেকে assign:** **সুপারিশ:** অনুমোদিত, `assignment_status` সরাসরি `accepted` (নিজের notification নয়)।
- [ ] **Re-assign:** rejected হলে assigner নতুন কাউকে assign করতে পারবে, `assignment_status` আবার `pending`।
- [ ] **Cross-team assign:** `403` নাকি `400`? **সুপারিশ:** `403` ("assignee must share a team with you"); assignee id নেই হলে `400`।
- [ ] **Self role change `403`, last admin demote `409`** (assignment এর hint অনুযায়ী)।
- [ ] **অন্যের todo `404`** (আপনার আগের নীতি রাখুন; assigner কে edit এ `403`)।
- [ ] **Delete:** assignment এ স্পষ্ট নেই। **সুপারিশ:** শুধু assigner delete করতে পারবে (hard delete)।
- [ ] **User delete হলে:** `assigner` → `CASCADE` (আগের মতো), `assignee` → `SET_NULL` (assignee বদলে গেলে assignment_status null/রিসেট)।

---

## ৪. Phase 1 – RBAC, Teams, Admin User Management

### 4.1 Model ও Migration
- [ ] **`accounts/models.py`**: `class Role(TextChoices): MEMBER, ADMIN`; `role = CharField(choices, default=MEMBER)` + `CheckConstraint(role in [...])` (আপনি অন্য model এ constraint ব্যবহার করেছেন, একই style)
- [ ] **`UserManager.create_superuser`**: `extra_fields.setdefault("role", "admin")`
- [ ] নতুন app **`teams`**:
  - `Team(name, created_at)` + `UniqueConstraint(Lower("name"))` (Category র মতো)
  - `Membership(user = OneToOneField(User, related_name="membership"), team = FK(Team, related_name="memberships"), joined_at)` → এক user = এক team DB level এ নিশ্চিত
- [ ] `makemigrations`; existing user দের `role=member` auto পাবে
- [ ] **`accounts/admin.py`**: `list_display`/`list_filter` এ `role`, fieldsets এ `role`; `teams/admin.py` এ Team + Membership inline
- [ ] **`accounts/forms.py`** এ `role` দরকার হলে যোগ করুন

### 4.2 Permission class
- [ ] `core/permissions.py` (নতুন): `IsAdminRole` → `is_authenticated and role == "admin"`
- [ ] Unauthenticated → `401`, member → `403` (DRF এ ডিফল্ট, `IsAuthenticated` আগে থেকেই default)

### 4.3 নতুন API

| Method | Endpoint | Access | কাজ |
|---|---|---|---|
| `GET` | `/api/auth/me` | Authenticated | `id, email, name, role, team{id,name}` |
| `GET` | `/api/teams` | Authenticated | সব predefined team (unpaginated, Category র মতো `pagination_class=None`) |
| `GET` | `/api/teams/{id}/members` | Authenticated, **নিজের team** হলে | Assignment picker (`id,name,email`) |
| `GET` | `/api/admin/users` | Admin | role, team, todo counts; search/filter/pagination |
| `PATCH` | `/api/admin/users/{id}` | Admin | `role`, `team_id` (null = team ছাড়া) |

- [ ] `accounts/urls.py` এ `me` যোগ (ফাইলে `auth/` prefix-এর নিচে); admin routes আলাদা `path("api/admin/", ...)`। **`config/urls.py` এ catch-all `api/<path:unknown>` সবার শেষে থাকতে হবে** (আপনার কমেন্ট অনুযায়ী) — নতুন path গুলো এর আগে বসান
- [ ] `user_payload()` (`accounts/serializers.py`) এ `role` ও `team` যোগ → register/login response এ আসবে (⚠️ নিচে "সতর্কতা" দেখুন: N+1)
- [ ] Todo count: `annotate(assigned_count=Count("assigned_todos"), created_count=Count("created_todos"), ...)` (distinct সতর্কতা: একাধিক Count একসাথে করলে `Count(..., distinct=True)` বা `filter=Q(...)` ব্যবহার করুন)

### 4.4 Admin business rules
- [ ] `request.user.pk == target.pk` এবং `role` পাঠানো হলে → `403` (শুধু role বদলাতে নিষেধ; নিজের team বদলাবে কিনা সিদ্ধান্ত নিন, সুপারিশ: নিষেধ নয়)
- [ ] Last admin: `transaction.atomic()` + `User.objects.select_for_update().filter(role="admin")` লক করে গুনুন; ১ জন থাকলে এবং target সেই admin হলে → `409`
  - ⚠️ SQLite এ `select_for_update` কিছু করে না (ignore হয়), কিন্তু Postgres এ (Render) কাজ করে। Test SQLite এ চলবে, তাই race test করতে যাবেন না; logic test করুন
- [ ] Team বদলানো = Membership `update_or_create(user=target, defaults={"team": team})`; `team_id=null` হলে membership delete
- [ ] Serializer এ `StrictIntegerChoiceField`/`StrictPrimaryKeyRelatedField` ব্যবহার, `http_method_names=["get","patch","head","options"]` (আপনার PUT-disabled নীতি)
- [ ] `PATCH` serializer শুধু `role`, `team_id` নেবে; `is_staff/is_superuser/email` ইত্যাদি **ইচ্ছাকৃতভাবে** field-ই নয়
- [ ] (Optional) role বদলালে user কে `role_changed` notification

### 4.5 Seed command
- [ ] `accounts/management/commands/seed_workspace.py` (idempotent: `get_or_create`)
- [ ] ≥২ team (Engineering, Design), ১ admin, ≥৪ member (প্রতি team এ কমপক্ষে ২ জন)
- [ ] Password env থেকে (`SEED_PASSWORD`) অথবা README তে দেখানো demo password; **`DEBUG=false` প্রোডাকশনে default এ চালাবেন না**
- [ ] `docker/entrypoint.sh` এ seed **ডিফল্ট চালাবেন না**; দরকারে `SEED_DEMO=true` flag দিয়ে optional করুন

### 4.6 Tests (Phase 1)
- [ ] `tests/factories.py`: `UserFactory` এ `role="member"`, নতুন `AdminUserFactory(role="admin")`, `TeamFactory`, `MembershipFactory`
- [ ] `tests/integration/conftest.py`: `admin_user` fixture এখন `is_staff/is_superuser` দিয়ে → `role="admin"` ও যোগ করুন (Category test ভাঙবে না কারণ `is_staff` রাখছেন)
- [ ] Member → সব admin endpoint `403`; unauthenticated `401`
- [ ] Self role change `403`; last admin demote `409`
- [ ] Register দিয়ে `role=admin` পাঠালে ignore হয়
- [ ] `/auth/me`, teams, members list

---

## ৫. Phase 2 – Todo পুনর্গঠন ও Assignment

### 5.1 `todos/models.py` ও migration (সবচেয়ে ঝুঁকিপূর্ণ ধাপ)
- [ ] `user` → `assigner` (`FK, CASCADE, related_name="created_todos"`)
- [ ] নতুন: `assignee` (`FK, SET_NULL, null, related_name="assigned_todos"`), `team` (`FK, SET_NULL, null`), `status` (choices + default `pending`), `assignment_status` (choices, `null=True`), `assigned_at`, `responded_at` (null)
- [ ] **Indexes নতুন করে**: বর্তমান ৫টি index (`todo_user_created_idx`, `todo_user_status_idx`, `todo_user_priority_idx`, `todo_user_open_due_idx` (partial, `is_completed=False` condition!), `todo_user_title_ci_idx`) সবাই `user` ও `is_completed` ব্যবহার করে।
  - **ধাপ:** (১) `RemoveIndex` ×৫ (২) `RenameField user→assigner` (৩) `status` যোগ + data migration (৪) `is_completed` সরান (৫) নতুন index `AddIndex`
  - নতুন query shape: `assigner`, `assignee` আলাদা index (`Q(assigner)|Q(assignee)` এর জন্য দুটো স্বতন্ত্র index ভালো), partial overdue index এর condition `status != completed`
  - Index নাম ৩০ অক্ষরের মধ্যে রাখুন
- [ ] **Data migration:** পুরোনো todo: `assigner = পুরোনো user`, `assignee = null`, `assignment_status = null`, `status` ম্যাপ
- [ ] নতুন `CheckConstraint`: `assignment_status` null ⇔ `assignee` null (অথবা self-assign হলে ব্যতিক্রম, সিদ্ধান্ত অনুযায়ী); `status in (...)`; `assignment_status in (...)`
- [ ] **Production (Render) এ migrate করার আগে DB backup।** `docker/entrypoint.sh` প্রতি deploy এ `migrate` চালায়, তাই push করলেই migration উড়ে যাবে

### 5.2 Scoping ও serializer
- [ ] `TodoViewSet.get_queryset()`: `Todo.objects.filter(Q(assigner=user) | Q(assignee=user)).select_related("category","assigner","assignee","team")`
- [ ] **`TodoSerializer.update()`** এর `filter(pk=..., user_id=instance.user_id)` → `filter(pk=instance.pk, assignee_id=instance.assignee_id)` (বা শুধু `pk`)। এটা ভুলে গেলে silent 404
- [ ] `TodoSerializer.Meta.fields` এ read-only: `assigner`, `assignee`, `team`, `assignment_status` (nested `{id,name}`)। `status` writable (শুধু assignee/creator-before-assign)
- [ ] `perform_create`: `serializer.save(assigner=request.user)`; optional `assignee_id` হলে validation (৫.৩) ও notification
- [ ] `todos/filters.py`: `?status=` ৩ মান; `?assignment_status=`; `?relation=assigned_to_me|assigned_by_me`; `?team=`; `filter_overdue` condition `is_completed=False` → `~Q(status="completed")`
- [ ] পুরোনো `lookup_value_regex`, `http_method_names` (PUT বন্ধ) রাখুন

### 5.3 Assign
- [ ] নতুন `@action(detail=True, methods=["post"], url_path="assign")` (router এ `/api/todos/{id}/assign` পাবেন)
- [ ] Body: `{ "assignee_id": 5 }` (`StrictPrimaryKeyRelatedField`)
- [ ] Validation: caller এর `membership` আছে; assignee র `membership.team_id == caller.membership.team_id`; নইলে `403`
- [ ] শুধু assigner (বা unassigned হলে creator) পারবে; অন্য → `404`/`403`
- [ ] `assignment_status=pending`, `assigned_at=now`, `team` সেট; `transaction.atomic()` এ notification তৈরি
- [ ] `POST /api/todos` এ `assignee_id` দিলে একই service function ব্যবহার করুন (**logic একজায়গায়**: `todos/services.py`)

### 5.4 Tests (Phase 2)
- [ ] **পুরোনো test গুলো ঠিক করুন:** `TodoFactory(user=...)`, `Todo.objects.get(...).user_id`, `create(..., user=999999)` ইত্যাদি `test_todo_api.py` ও `test_models.py`, `test_serializers.py`, `test_filters.py` এ আছে → `assigner` এ বদলাতে হবে
- [ ] Same-team assign সফল; cross-team `403`; অন্য teammate detail → `404`; list শুধু নিজের সম্পর্কিত

---

## ৬. Phase 3 – Accept/Reject, Strict Permission, Notifications

### 6.1 Accept / Reject
- [ ] `@action(detail=True, methods=["post"])` `accept` ও `reject`
- [ ] শুধু assignee; assigner → `403`; অন্য → `404`
- [ ] `assignment_status != pending` হলে `409`
- [ ] `transaction.atomic()` + `select_for_update()` + conditional update (`filter(pk, assignment_status="pending").update(...)` ফেরত rows=0 হলে `409`) — SQLite এও নিরাপদ এই conditional-update পদ্ধতি
- [ ] Assigner কে notification; optional `reason`

### 6.2 Strict edit permission
- [ ] `todos/permissions.py` (নতুন): `CanEditTodo`, object-level:
  - Assignee → অনুমোদিত
  - Assigner (assignee নয়, এবং todo assigned) → `403`
  - Unassigned এ creator → অনুমোদিত (সিদ্ধান্ত অনুযায়ী)
- [ ] ⚠️ `get_queryset` এ assigner কে পেলেও object permission এ `403`; অন্য কেউ queryset এ নেই বলে `404` — দুই স্তর আলাদা রাখুন
- [ ] `destroy` এ শুধু assigner
- [ ] Rejected todo তে edit কী হবে সিদ্ধান্ত নিন (সুপারিশ: রিজেক্টেড হলে assignee আর edit করতে পারবে না)

### 6.3 Notification
- [ ] নতুন app **`notifications`**: `Notification(recipient FK CASCADE, type, message, todo FK null SET_NULL, link CharField, is_read, created_at, read_at)`
- [ ] Index: `(recipient, is_read, -created_at, -id)`
- [ ] **Safe link:** server নিজে `f"/todos/{todo.pk}"` বানাবে; কখনো client input নয়; `CheckConstraint`/validator: `/` দিয়ে শুরু, `//` বা `://` নেই
- [ ] `notifications/services.py`: `notify_assigned()`, `notify_accepted()`, `notify_rejected()`, `notify_role_changed()`; state পরিবর্তনের **একই `atomic` ব্লকে** তৈরি (signal নয়, তাতে duplicate/ordering ঝামেলা)

### 6.4 Notification API

| Method | Endpoint | কাজ |
|---|---|---|
| `GET` | `/api/notifications` | নিজের list (paginated, `?is_read=`) |
| `GET` | `/api/notifications/unread-count` | `{"count": n}` |
| `POST` | `/api/notifications/{id}/read` | একটি read (অন্যেরটা `404`) |
| `POST` | `/api/notifications/read-all` | সব read |

- [ ] **Throttle:** `settings.py` এর `THROTTLE_RATES` এ নতুন scope (যেমন `"notifications": "120/min"`) + `ScopedRateThrottle`; নইলে polling এ `user: 100/min` শেষ হয়ে বাকি API (`429`) আটকাবে। এখানে `DEFAULT_THROTTLE_CLASSES` এ `UserRateThrottle` আছে, তাই notification view এ `throttle_classes = [ScopedRateThrottle]` দিয়ে default override করুন
- [ ] সব query `recipient=request.user` দিয়ে scope

### 6.5 Tests (Phase 3)
- [ ] Assignee edit/accept/reject পারে; assigner edit → `403`
- [ ] Assign/accept/reject এ ঠিক notification তৈরি (recipient, type, link)
- [ ] অন্যের notification দেখা/read → `404`; unread count কমে
- [ ] দুইবার accept → `409`

---

## ৭. Phase 4 – Backend Finish

- [ ] **Docs:** নতুন view গুলোতে `extend_schema` (আপনার `ErrorResponseSerializer`, `ValidationErrorResponseSerializer` দিয়ে `403/404/409` দেখান); `python manage.py spectacular --file schema.yml --validate`; `tests/integration/test_documentation_api.py` চালিয়ে দেখুন
- [ ] **README:** নতুন API map, seed account/team, decisions, limitations। "Known limitations" এ লিখুন SQLite এ `select_for_update` কাজ করে না
- [ ] **`.env.example`** এ নতুন কিছু (যেমন `SEED_PASSWORD`) থাকলে যোগ
- [ ] `requriements.txt` মুছুন; `.gitignore` যাচাই
- [ ] `docker compose --profile test run --rm test` এ সব test pass

---

## ৮. Bonus – Admin Dashboard (Backend)

| Method | Endpoint | কাজ |
|---|---|---|
| `GET` | `/api/admin/dashboard/overview` | users, teams, todos, incomplete, completed, pending assignments, completion rate |
| `GET` | `/api/admin/dashboard/users` | user-wise stats + ratio |
| `GET` | `/api/admin/dashboard/teams` | team-wise stats |
| `GET` | `/api/admin/dashboard/activity` | সাম্প্রতিক activity (assigned_at/responded_at/updated_at থেকে) |
| `GET` | `/api/admin/users/{id}/todos` | সেই user এর todo (read-only) |
| `GET` | `/api/admin/todos/{id}` | detail (read-only) |

- [ ] সব view `IsAdminRole`, `http_method_names = ["get","head","options"]` (`ReadOnlyModelViewSet`)
- [ ] সাধারণ `/api/todos` এ admin এর কোনো বিশেষ অধিকার **দেবেন না** (আপনার `get_queryset` কমেন্টের নীতি বজায় থাকবে)
- [ ] Aggregation DB তে (`Count(filter=Q(...))`); ০ এ ভাগ handle
- [ ] Metric সংজ্ঞা README তে লিখুন (rejected todo completion rate এ ধরবেন কিনা)
- [ ] Bottleneck: ৭+ দিন pending assignment, overdue, reject-rate বেশি এমন user/team
- [ ] Test: member `403`; admin POST/PATCH/DELETE → `405`; ছোট fixture এ metric ঠিক

---

## ৯. Frontend (Next.js) – সংক্ষেপে

- [ ] Next.js 15 App Router + plain `fetch` (আলাদা folder/repo, যেমন `web/` বা `frontend/`)
- [ ] **Token browser এ নয়:** Next.js Route Handler/proxy backend `/api/auth/login` কল করে `access/refresh` **server-side** রাখবে (browser পাবে শুধু opaque `httpOnly` session cookie); আপনার backend এর `refresh` rotation + blacklist এই proxy ই চালাবে (access ১৫ মিনিট, তাই proxy কে 401 এ refresh করতে হবে)
- [ ] Pages: login, register, todos, todo details, admin users, notifications (+ dashboard)
- [ ] Details: Accept/Reject শুধু assignee ও `assignment_status=pending`; edit শুধু assignee
- [ ] Bell + unread badge; polling (`document.visibilityState`); `not-found`, error boundary; Jest tests; mobile responsive

---

## ১০. কাজের ক্রম

1. সিদ্ধান্ত (৩ নং) চূড়ান্ত
2. `role` + `teams` app + migration + seed + admin API + tests → **Phase 1 শেষ**
3. Todo migration (index remove → rename → status → index add), serializer `update()` ঠিক, queryset scope
4. পুরোনো tests ঠিক করুন (`user=` → `assigner=`) → সব green করুন
5. Assign + same-team validation
6. Notification app + API + throttle scope
7. Accept/reject + strict edit permission
8. `schema.yml`, README, cleanup
9. Frontend
10. Bonus dashboard

---

## ১১. সতর্কতা

- **Migration আগে নিজের মেশিনে আসল ডেটাসহ চালিয়ে দেখুন;** Render এ push মানেই `migrate`
- `user_payload()` এ `team` যোগ করলে প্রতি login/register এ একটা বাড়তি query; `select_related("membership__team")` ব্যবহার করুন
- দুই `Count` একসাথে annotate এ join গুণ হয়ে সংখ্যা ভুল আসে: `Count("...", distinct=True)` ব্যবহার করুন
- `Q(assigner=me) | Q(assignee=me)` এ duplicate নেই (একই row একবারই), তবে অন্য join যোগ করলে `.distinct()` দরকার হতে পারে
- Permission শুধু UI তে নয়; প্রতিটি rule এর backend test থাকতে হবে