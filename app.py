import hashlib
import hmac
import secrets
import string
from datetime import datetime, timezone

import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Ballon d’Or Battle", page_icon="🏆", layout="centered")

NOMINEES = [
    "Jude Bellingham", "Pau Cubarsi", "Marc Cucurella", "Ousmane Dembélé",
    "Luis Diaz", "Bruno Fernandes", "Gabriel", "Erling Haaland",
    "Achraf Hakimi", "Harry Kane", "Khvicha Kvaratskhelia", "Lamine Yamal",
    "Sadio Mané", "Marquinhos", "Lautaro Martinez", "Kylian Mbappé",
    "Nuno Mendes", "Lionel Messi", "João Névés", "Michael Olise",
    "Willian Pacho", "Julián Quiñones", "Declan Rice", "Rodri",
    "Fabián Ruiz", "William Saliba", "Ferran Torres", "Dayot Upamecano",
    "Vinícius Jr.", "Vitinha",
]
BASE_POINTS = {1: 20, 2: 15, 3: 12, 4: 10, 5: 8, 6: 6, 7: 5, 8: 4, 9: 3, 10: 2}
PIN_ITERATIONS = 310_000


# ---------- Configuration and helpers ----------
@st.cache_resource
def get_supabase():
    url = st.secrets.get("SUPABASE_URL", "").strip().rstrip("/")
    # Use a server-side service-role key. Never put this key in a public/client app.
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        # Backwards-compatible fallback, but it must also be the service-role key.
        key = st.secrets.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        st.error(
            "Configuration Supabase manquante. Dans Streamlit → Settings → Secrets, "
            "renseigne SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY."
        )
        st.stop()
    if "/rest/v1" in url or "/dashboard" in url:
        st.error("SUPABASE_URL doit être l’URL de base, par exemple https://xxxx.supabase.co, sans /rest/v1.")
        st.stop()
    return create_client(url, key)


db = get_supabase()


def pin_hash(pin: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PIN_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        candidate = pin_hash(pin, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def rows(table: str, **filters):
    query = db.table(table).select("*")
    for key, value in filters.items():
        query = query.eq(key, value)
    return query.execute().data or []


def get_game(code: str):
    found = db.table("games").select("*").eq("code", code.strip().upper()).limit(1).execute().data or []
    return found[0] if found else None


def get_profile_by_nickname(nickname: str):
    key = nickname.strip().casefold()
    found = db.table("profiles").select("*").eq("nickname_key", key).limit(1).execute().data or []
    return found[0] if found else None


def is_member(game_id: str, player_id: str) -> bool:
    found = db.table("game_players").select("id").eq("game_id", game_id).eq("player_id", player_id).limit(1).execute().data or []
    return bool(found)


def add_member(game_id: str, player_id: str):
    if not is_member(game_id, player_id):
        db.table("game_players").insert({"game_id": game_id, "player_id": player_id}).execute()


def make_game_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if not get_game(code):
            return code
    raise RuntimeError("Impossible de générer un code de partie unique. Réessaie.")


def current_profile():
    return st.session_state.get("profile")


def logout():
    for key in ("profile", "selected_game_id"):
        st.session_state.pop(key, None)
    st.rerun()


def official_results(game_id: str):
    return sorted(rows("official_results", game_id=game_id), key=lambda x: x["rank"])


def player_picks(game_id: str, player_id: str):
    return sorted(
        rows("picks", game_id=game_id, player_id=player_id),
        key=lambda x: x["predicted_rank"],
    )


def pick_score_details(picks, results):
    """Return the per-pick scoring breakdown using the same rules as calculate_score."""
    if len(results) != 10:
        return None
    actual = {r["nominee_name"]: int(r["rank"]) for r in results}
    details = []
    for pick in sorted(picks, key=lambda x: int(x["predicted_rank"])):
        predicted_rank = int(pick["predicted_rank"])
        nominee = pick["nominee_name"]
        if nominee in actual:
            actual_rank = actual[nominee]
            points = max(0, BASE_POINTS[actual_rank] - 3 * abs(predicted_rank - actual_rank))
            actual_label = f"{actual_rank}e"
        else:
            points = -2
            actual_label = "Hors Top 10"
        details.append({
            "Place prédite": predicted_rank,
            "Joueur pronostiqué": nominee,
            "Place officielle": actual_label,
            "Points gagnés": points,
        })
    return details


def calculate_score(picks, results):
    details = pick_score_details(picks, results)
    if details is None:
        return None
    return sum(row["Points gagnés"] for row in details)


def game_link(code: str):
    try:
        base = st.context.url.split("?")[0]
        return f"{base}?join={code}"
    except Exception:
        return f"Code à partager : {code}"


# ---------- Page header ----------
st.title("🏆 Ballon d’Or Battle")
st.caption("Pronos entre amis · Top 10 · Classement et scores partagés")

profile = current_profile()

# ---------- Login / registration ----------
if not profile:
    login_tab, create_tab = st.tabs(["Me connecter", "Créer mon profil"])
    with login_tab:
        st.subheader("Retrouver mes parties")
        with st.form("login_form"):
            nickname = st.text_input("Ton pseudo", max_chars=24, key="login_nickname")
            pin = st.text_input("Ton code personnel", type="password", max_chars=64, key="login_pin")
            submitted = st.form_submit_button("Me connecter", width="stretch")
        if submitted:
            try:
                existing = get_profile_by_nickname(nickname)
                if not nickname.strip() or not pin:
                    st.error("Renseigne ton pseudo et ton code personnel.")
                elif not existing or not verify_pin(pin, existing["pin_hash"]):
                    st.error("Pseudo ou code incorrect. Si c’est ta première visite, crée ton profil.")
                else:
                    st.session_state.profile = {
                        "id": existing["id"],
                        "nickname": existing["nickname"],
                    }
                    st.rerun()
            except Exception as e:
                st.error(f"Connexion impossible : {e}")

    with create_tab:
        st.subheader("Créer un profil")
        st.info("Choisis un pseudo unique et un code personnel que tu pourras retenir. Aucun e-mail n’est demandé.")
        with st.form("register_form"):
            new_nickname = st.text_input("Pseudo à utiliser dans les parties", max_chars=24, key="new_nickname")
            new_pin = st.text_input("Code personnel (6 caractères minimum)", type="password", max_chars=64, key="new_pin")
            confirm_pin = st.text_input("Confirme le code personnel", type="password", max_chars=64, key="confirm_pin")
            registered = st.form_submit_button("Créer mon profil", width="stretch")
        if registered:
            normalized = new_nickname.strip()
            if len(normalized) < 2:
                st.error("Le pseudo doit contenir au moins 2 caractères.")
            elif len(new_pin) < 6:
                st.error("Le code personnel doit contenir au moins 6 caractères.")
            elif new_pin != confirm_pin:
                st.error("Les deux codes ne correspondent pas.")
            else:
                try:
                    if get_profile_by_nickname(normalized):
                        st.error("Ce pseudo est déjà utilisé. Choisis-en un autre.")
                    else:
                        created = db.table("profiles").insert({
                            "nickname": normalized,
                            "nickname_key": normalized.casefold(),
                            "pin_hash": pin_hash(new_pin),
                        }).execute().data
                        if created:
                            st.success("Profil créé ! Connecte-toi dans l’onglet « Me connecter ».")
                            st.rerun()
                        else:
                            st.error("Le profil n’a pas pu être créé. Réessaie.")
                except Exception as e:
                    st.error(f"Création du profil impossible : {e}")
    st.stop()

# ---------- Logged-in dashboard ----------
profile = current_profile()
st.write(f"Connecté·e en tant que **{profile['nickname']}**")
if st.button("Se déconnecter", key="logout"):
    logout()

# Support direct invitation links ?join=CODE
join_code = st.query_params.get("join")
if isinstance(join_code, list):
    join_code = join_code[0] if join_code else None

if join_code:
    st.info(f"Invitation à rejoindre la partie **{str(join_code).upper()}**")
    if st.button("Rejoindre cette partie", key="join_from_link", width="stretch"):
        try:
            game = get_game(str(join_code))
            if not game:
                st.error("Cette partie n’existe pas (ou le code est incorrect).")
            elif game["status"] != "open" or bool(game.get("predictions_locked", False)):
                st.warning("Cette partie n’accepte plus de nouveaux joueurs : les pronostics sont verrouillés ou la partie est terminée.")
            else:
                add_member(game["id"], profile["id"])
                st.session_state.selected_game_id = game["id"]
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error(f"Impossible de rejoindre la partie : {e}")

create_tab, join_tab = st.tabs(["➕ Créer une partie", "🔗 Rejoindre une partie"])
with create_tab:
    st.subheader("Nouvelle partie")
    game_name = st.text_input("Nom de la partie", placeholder="Ex. Ballon d’Or entre amis", max_chars=60)
    if st.button("Créer la partie", width="stretch", key="create_game"):
        try:
            code = make_game_code()
            result = db.table("games").insert({
                "code": code,
                "name": game_name.strip() or f"Partie de {profile['nickname']}",
                "admin_player_id": profile["id"],
                "status": "open",
            }).execute().data
            if result:
                game = result[0]
                add_member(game["id"], profile["id"])
                st.session_state.selected_game_id = game["id"]
                st.success("Partie créée ! Tu es l’admin de cette partie.")
                st.code(code)
                st.code(game_link(code))
                st.rerun()
        except Exception as e:
            st.error(f"Création impossible : {e}")

with join_tab:
    st.subheader("Rejoindre une partie")
    with st.form("join_form"):
        code_to_join = st.text_input("Code de la partie", max_chars=12).strip().upper()
        join_submitted = st.form_submit_button("Rejoindre", width="stretch")
    if join_submitted:
        try:
            game = get_game(code_to_join)
            if not game:
                st.error("Code introuvable. Vérifie le code d’invitation.")
            elif game["status"] != "open" or bool(game.get("predictions_locked", False)):
                st.error("Cette partie n’accepte plus de nouveaux joueurs : les pronostics sont verrouillés ou la partie est fermée.")
            else:
                add_member(game["id"], profile["id"])
                st.session_state.selected_game_id = game["id"]
                st.success(f"Tu as rejoint « {game['name']} ».")
                st.rerun()
        except Exception as e:
            st.error(f"Impossible de rejoindre la partie : {e}")

# Dashboard: show both open and closed games the player belongs to
st.divider()
st.header("Mes parties")
try:
    memberships = rows("game_players", player_id=profile["id"])
    member_game_ids = [m["game_id"] for m in memberships]
    games = []
    if member_game_ids:
        games = db.table("games").select("*").in_("id", member_game_ids).order("created_at", desc=True).execute().data or []
    if not games:
        st.caption("Tu n’as pas encore de partie. Crée-en une ou rejoins-en une avec un code.")
    for game in games:
        member_rows = rows("game_players", game_id=game["id"])
        member_ids = [m["player_id"] for m in member_rows]
        people = []
        if member_ids:
            people = db.table("profiles").select("id,nickname").in_("id", member_ids).execute().data or []
        is_admin = game["admin_player_id"] == profile["id"]
        with st.container(border=True):
            st.subheader(game["name"])
            if game["status"] == "closed":
                status_label = "🏁 Terminée"
            elif bool(game.get("predictions_locked", False)):
                status_label = "🔒 Pronostics verrouillés · classement révélé"
            else:
                status_label = "🟢 En cours · pronostics ouverts"
            st.caption(f"{status_label} · Code : {game['code']} · {len(member_rows)} joueur(s)" + (" · Admin" if is_admin else ""))
            st.write("Joueurs : " + ", ".join(p["nickname"] for p in people))
            button_label = "Ouvrir la partie" if game["status"] == "open" else "Voir les résultats"
            if st.button(button_label, key=f"open_{game['id']}", width="stretch"):
                st.session_state.selected_game_id = game["id"]
                st.rerun()
except Exception as e:
    st.error(f"Impossible de charger le tableau de bord : {e}")

# ---------- Selected game workspace ----------
selected_id = st.session_state.get("selected_game_id")
if selected_id:
    selected = db.table("games").select("*").eq("id", selected_id).limit(1).execute().data or []
    if selected and is_member(selected_id, profile["id"]):
        game = selected[0]
        st.divider()
        st.header(f"🎮 {game['name']}")
        st.caption(f"Code d’invitation : {game['code']}")
        st.code(game_link(game["code"]))
        is_admin = game["admin_player_id"] == profile["id"]

        members = rows("game_players", game_id=game["id"])
        member_ids = [m["player_id"] for m in members]
        member_profiles = db.table("profiles").select("id,nickname").in_("id", member_ids).execute().data or [] if member_ids else []
        nickname_by_id = {p["id"]: p["nickname"] for p in member_profiles}

        picks_tab, results_tab, leaderboard_tab = st.tabs(["Mes pronostics", "Classement officiel", "Scores"])
        with picks_tab:
            st.subheader("Classe ton Top 10")
            current_picks = player_picks(game["id"], profile["id"])
            existing_by_rank = {int(p["predicted_rank"]): p["nominee_name"] for p in current_picks}
            predictions_locked = bool(game.get("predictions_locked", False))
            if game["status"] != "open" or predictions_locked:
                if predictions_locked and game["status"] == "open":
                    st.info("🔒 Les pronostics sont verrouillés. Le classement officiel est révélé, mais les scores finaux restent masqués jusqu’à la clôture.")
                else:
                    st.info("Cette partie est clôturée : les pronostics ne sont plus modifiables.")
            else:
                st.caption("Chaque joueur peut choisir 10 noms distincts. Tes choix restent modifiables jusqu’au verrouillage par l’admin.")
                with st.form(f"picks_{game['id']}"):
                    chosen = []
                    for rank in range(1, 11):
                        default_name = existing_by_rank.get(rank, NOMINEES[min(rank - 1, len(NOMINEES) - 1)])
                        default_index = NOMINEES.index(default_name) if default_name in NOMINEES else rank - 1
                        chosen.append(st.selectbox(f"{rank}ᵉ place", NOMINEES, index=default_index, key=f"pick_{game['id']}_{rank}"))
                    save_picks = st.form_submit_button("Enregistrer mon Top 10", width="stretch")
                if save_picks:
                    if len(set(chosen)) != 10:
                        st.error("Chaque joueur doit choisir 10 noms différents.")
                    else:
                        try:
                            db.table("picks").delete().eq("game_id", game["id"]).eq("player_id", profile["id"]).execute()
                            payload = [{
                                "game_id": game["id"],
                                "player_id": profile["id"],
                                "predicted_rank": rank,
                                "nominee_name": nominee,
                            } for rank, nominee in enumerate(chosen, start=1)]
                            db.table("picks").insert(payload).execute()
                            st.success("Pronostics enregistrés !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Enregistrement impossible : {e}")
            if current_picks:
                st.write("Ton Top 10 enregistré :")
                for pick in current_picks:
                    st.write(f"**{pick['predicted_rank']}.** {pick['nominee_name']}")

        with results_tab:
            st.subheader("Classement officiel du Ballon d’Or")
            results = official_results(game["id"])
            predictions_locked = bool(game.get("predictions_locked", False))

            if is_admin:
                st.caption("Tu es l’admin de cette partie. Tant que les pronostics ne sont pas verrouillés, le classement officiel reste un brouillon modifiable par toi seul.")
                if game["status"] == "open" and not predictions_locked:
                    old_by_rank = {int(r["rank"]): r["nominee_name"] for r in results}
                    with st.form(f"official_{game['id']}"):
                        official_chosen = []
                        for rank in range(1, 11):
                            old_name = old_by_rank.get(rank, NOMINEES[rank - 1])
                            old_index = NOMINEES.index(old_name) if old_name in NOMINEES else rank - 1
                            official_chosen.append(st.selectbox(f"Classement officiel — {rank}ᵉ", NOMINEES, index=old_index, key=f"official_pick_{game['id']}_{rank}"))
                        save_official = st.form_submit_button("Enregistrer / modifier le classement officiel", width="stretch")
                    if save_official:
                        if len(set(official_chosen)) != 10:
                            st.error("Le classement officiel doit contenir 10 noms différents.")
                        else:
                            try:
                                db.table("official_results").delete().eq("game_id", game["id"]).execute()
                                db.table("official_results").insert([{
                                    "game_id": game["id"], "rank": rank, "nominee_name": nominee
                                } for rank, nominee in enumerate(official_chosen, start=1)]).execute()
                                st.success("Classement officiel enregistré en brouillon. Il n’est pas encore visible des autres joueurs.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Enregistrement du classement impossible : {e}")

                    st.write(f"Pronostics complets : {sum(1 for m in members if len(player_picks(game['id'], m['player_id'])) == 10)}/{len(members)} joueurs.")
                    if len(results) == 10:
                        st.warning("Le verrouillage est définitif : tous les joueurs ne pourront plus modifier leur Top 10 et le classement officiel sera révélé.")
                        if st.button("🔒 Verrouiller les pronostics et révéler le classement réel", key=f"lock_{game['id']}", width="stretch"):
                            try:
                                db.table("games").update({"predictions_locked": True}).eq("id", game["id"]).eq("status", "open").execute()
                                st.success("Pronostics verrouillés et classement officiel révélé !")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Verrouillage impossible. Vérifie que la colonne predictions_locked a été ajoutée dans Supabase. Détail : {e}")
                    else:
                        st.info("Enregistre d’abord les 10 places officielles pour pouvoir verrouiller les pronostics.")
                elif predictions_locked and game["status"] == "open":
                    st.success("🔒 Pronostics verrouillés. Le classement réel est révélé ; les scores finaux seront affichés à la clôture.")
                    if len(results) == 10 and st.button("🏁 Clôturer la partie et afficher les scores finaux", key=f"close_{game['id']}", width="stretch"):
                        try:
                            db.table("games").update({"status": "closed", "closed_at": datetime.now(timezone.utc).isoformat()}).eq("id", game["id"]).execute()
                            st.success("Partie clôturée. Les scores finaux sont maintenant disponibles.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Clôture impossible : {e}")
                elif game["status"] == "closed":
                    st.success("Cette partie est clôturée : pronostics et classement officiel sont verrouillés.")
            elif not predictions_locked:
                st.info("Le classement officiel est masqué jusqu’à ce que l’admin verrouille les pronostics. Cela évite d’influencer les choix des joueurs.")

            # The real ranking is visible to everyone only after the admin locks the predictions.
            if predictions_locked or game["status"] == "closed":
                if results:
                    st.markdown("#### Classement officiel révélé")
                    for result in results:
                        st.write(f"**{result['rank']}.** {result['nominee_name']}")
                else:
                    st.warning("Le classement officiel n’a pas encore été renseigné.")
            elif is_admin and results:
                st.caption("Aperçu privé du classement officiel (visible uniquement par l’admin avant le verrouillage).")
                for result in results:
                    st.write(f"**{result['rank']}.** {result['nominee_name']}")

        with leaderboard_tab:
            st.subheader("Classement des joueurs")
            results = official_results(game["id"])
            if game["status"] != "closed":
                if bool(game.get("predictions_locked", False)):
                    st.info("Les pronostics sont verrouillés et le classement officiel est révélé. Les scores et le classement des joueurs seront affichés lorsque l’admin clôturera la partie.")
                else:
                    st.info("Les scores restent masqués jusqu’à la clôture de la partie, après verrouillage des pronostics et révélation du classement officiel.")
            elif len(results) == 10:
                leaderboard = []
                for member in members:
                    pid = member["player_id"]
                    picks = player_picks(game["id"], pid)
                    score = calculate_score(picks, results) if len(picks) == 10 else None
                    leaderboard.append({
                        "Joueur": nickname_by_id.get(pid, "Joueur"),
                        "Pronostics validés": "Oui" if len(picks) == 10 else f"{len(picks)}/10",
                        "Points": score if score is not None else "Non calculable (Top 10 incomplet)",
                    })
                leaderboard.sort(key=lambda x: x["Points"] if isinstance(x["Points"], int) else -10**9, reverse=True)
                st.dataframe(leaderboard, hide_index=True, width="stretch")
                st.caption("Barème : 20, 15, 12, 10, 8, 6, 5, 4, 3, 2 points selon la place officielle, moins 3 points par place d’écart (minimum 0) ; −2 points pour un nom hors du Top 10 officiel.")
                st.markdown("#### Détail des pronostics de chaque joueur")
                for member in members:
                    pid = member["player_id"]
                    player_name = nickname_by_id.get(pid, "Joueur")
                    picks = player_picks(game["id"], pid)
                    if len(picks) == 10:
                        details = pick_score_details(picks, results)
                        total = sum(row["Points gagnés"] for row in details)
                        with st.expander(f"{player_name} — {total} points"):
                            st.dataframe(details, hide_index=True, width="stretch")
                    else:
                        with st.expander(f"{player_name} — pronostics incomplets"):
                            st.write(f"Ce joueur a enregistré {len(picks)}/10 pronostics. Son score ne peut pas encore être calculé.")
            else:
                st.warning("La partie est clôturée, mais le classement officiel ne contient pas 10 places. Contacte l’admin.")

else:
    st.caption("Choisis une partie dans « Mes parties » pour voir tes pronostics, le classement officiel et les scores.")
