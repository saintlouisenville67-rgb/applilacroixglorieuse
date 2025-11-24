import streamlit as st
import pandas as pd
from datetime import date
from google.oauth2.service_account import Credentials
import gspread
import bcrypt # Utiliser bcrypt pour hacher les mots de passe

# --- Configuration de la Page et Style ---
st.set_page_config(
    page_title="Parcours de Carême LaCroixglorieuse",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("🕊️ Parcours de Carême : La Croix Glorieuse")
st.markdown("---")

# --- Configuration des Noms de Feuilles (À VÉRIFIER) ---
# **ASSUREZ-VOUS QUE CES NOMS CORRESPONDENT EXACTEMENT À VOS GOOGLE SHEETS**
UTILISATEURS_SHEET_NAME = "Utilisateurs LaCroixglorieuse" 
CARÊME_SHEET_NAME = "Contenu Carême LaCroixglorieuse" 

# --- Fonctions de Connexion Google Sheets ---

# Cache la connexion au client gspread pour éviter de la refaire à chaque fois.
@st.cache_resource(ttl=3600)
def get_gspread_client():
    """Initialise et retourne le client gspread en utilisant les secrets."""
    try:
        creds_json = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_json,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets. Vérifiez .streamlit/secrets.toml : {e}")
        return None

def load_data(sheet_name):
    """Charge les données d'une feuille spécifique en DataFrame."""
    client = get_gspread_client()
    if client:
        try:
            # Ouvrir le classeur par son nom et sélectionner la première feuille
            sheet = client.open(sheet_name).sheet1
            data = sheet.get_all_records()
            return pd.DataFrame(data), sheet # Retourne aussi l'objet sheet pour l'écriture
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"La feuille '{sheet_name}' n'a pas été trouvée. Vérifiez le nom et le partage.")
            return pd.DataFrame(), None
        except Exception as e:
            st.error(f"Erreur lors du chargement des données de {sheet_name}: {e}")
            return pd.DataFrame(), None
    return pd.DataFrame(), None

# Chargement initial des bases de données
df_users, sheet_users = load_data(UTILISATEURS_SHEET_NAME)
df_careme, _ = load_data(CARÊME_SHEET_NAME) # Pas besoin de l'objet sheet pour le contenu

# --- Fonctions d'Authentification Sécurisée ---

def hash_password(password):
    """Hache le mot de passe en utilisant le sel sécurisé."""
    password_bytes = password.encode('utf-8')
    # Utilisez gensalt() pour générer un nouveau sel et hacher
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')

def check_password(password, hashed_password):
    """Vérifie le mot de passe saisi par rapport au haché stocké."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def register_user(email, password, sheet):
    """Ajoute un nouvel utilisateur à la feuille Google Sheets."""
    if sheet is None:
        st.error("Impossible de se connecter à la base d'utilisateurs pour l'inscription.")
        return False
        
    # Vérification rapide si l'email est déjà dans le DataFrame (qui est chargé au début)
    if email in df_users['Email'].tolist():
        st.warning("Cet e-mail est déjà utilisé. Veuillez vous connecter.")
        return False

    if not email or not password:
        st.warning("L'e-mail et le mot de passe sont obligatoires.")
        return False

    try:
        # Hachage et enregistrement des données
        hashed_pwd = hash_password(password)
        
        # NOTE: Les noms de colonnes dans la feuille DOIVENT être : 
        # Email | Mot_de_Passe_Haché | Date_Inscription
        new_row = [email, hashed_pwd, date.today().strftime('%Y-%m-%d')]
        sheet.append_row(new_row)
        st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'inscription : {e}")
        return False

# --- Interfaces Utilisateur (UI) ---

def login_ui():
    """Affiche l'interface de connexion et d'inscription."""
    st.markdown("## 🔑 Connexion")
    
    with st.form("login_form"):
        email = st.text_input("Email de connexion", key="login_email").lower().strip()
        password = st.text_input("Mot de Passe", type="password", key="login_password")
        submitted = st.form_submit_button("Se Connecter")

        if submitted:
            if df_users.empty:
                st.error("La base d'utilisateurs est vide ou n'a pas pu être chargée.")
                return
                
            # Recherche de l'utilisateur dans le DataFrame chargé
            user_data = df_users[df_users['Email'] == email]
            
            if not user_data.empty:
                # Vérification du mot de passe
                # Assurez-vous que la colonne a le nom exact: 'Mot_de_Passe_Haché'
                hashed_pwd = user_data.iloc[0]['Mot_de_Passe_Haché']
                
                if check_password(password, hashed_pwd):
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.session_state.is_registering = False 
                    # Redirection immédiate pour afficher le contenu
                    st.rerun() 
                else:
                    st.error("Mot de passe incorrect.")
            else:
                st.error("Utilisateur non trouvé. Veuillez vérifier votre email ou vous inscrire.")

    # Bouton pour basculer vers le mode inscription
    st.markdown("---")
    if st.button("Pas encore inscrit ? Créer un compte"):
        st.session_state.is_registering = True
        st.rerun()

def register_ui():
    """Affiche l'interface d'inscription."""
    st.markdown("## 📝 Inscription")
    
    with st.form("register_form"):
        new_email = st.text_input("Votre Email (Inscription)").lower().strip()
        new_password = st.text_input("Créez un Mot de Passe", type="password")
        submitted = st.form_submit_button("M'inscrire")
        
        if submitted:
            if register_user(new_email, new_password, sheet_users):
                # Redirection vers la connexion après l'inscription réussie
                st.session_state.is_registering = False
                st.rerun()

    # Bouton pour revenir à la connexion
    st.markdown("---")
    if st.button("Retour à la connexion"):
        st.session_state.is_registering = False
        st.rerun()

def display_careme_content(user_email):
    """Affiche le contenu quotidien du parcours de Carême."""
    
    st.success(f"Bienvenue sur votre parcours, {user_email.split('@')[0]}!")

    # 1. Déterminer le jour de Carême
    # Utilisation de la date d'aujourd'hui pour l'exemple.
    today_str = date.today().strftime('%Y-%m-%d')
    
    st.header(f"Parcours du Jour : {today_str}")
    
    # Filtrer le DataFrame pour le contenu du jour
    content_today = df_careme[df_careme['Date'] == today_str]
    
    if content_today.empty or df_careme.empty:
        st.warning("Le contenu du Carême pour aujourd'hui n'est pas encore disponible.")
        st.info("Veuillez remplir votre Google Sheet 'Contenu Carême LaCroixglorieuse' avec la date d'aujourd'hui (format YYYY-MM-JJ) et vérifier que les noms de colonnes sont corrects.")
        
        # Afficher un contenu de base pour l'attente
        st.subheader("En attendant le contenu...")
        st.write("Nous vous invitons à la prière et à la méditation de la Parole de Dieu.")
        return

    # --- Affichage du Contenu Quotidien ---
    
    # Récupérer la ligne unique du jour
    day_data = content_today.iloc[0]

    st.markdown("---")
    
    # Image (Colonne : URL_Image)
    image_url = day_data.get('URL_Image')
    if image_url:
        st.image(image_url, caption=f"Image du jour : {day_data.get('Jour', 'Carême')}")
    else:
        st.info(" (URL d'image manquante. Veuillez remplir la colonne 'URL_Image' dans votre feuille)")

    # Texte sur le Curé d'Ars (Colonne : Texte_Cure_dArs)
    st.subheader("📖 La Vie du Curé d'Ars")
    st.markdown(day_data.get('Texte_Cure_dArs', "**Contenu manquant.** Veuillez remplir la colonne 'Texte_Cure_dArs'."))

    # Citation Parole de Dieu (Colonne : Citation_Parole)
    st.subheader("✝️ Parole de Dieu")
    st.code(day_data.get('Citation_Parole', "**Contenu manquant.** Veuillez remplir la colonne 'Citation_Parole'."), language='text')

    # Effort du Jour (Colonne : Effort_Jour)
    st.subheader("💪 Votre Effort du Jour")
    st.info(day_data.get('Effort_Jour', "**Contenu manquant.** Veuillez remplir la colonne 'Effort_Jour'."))
    
    st.markdown("---")
    st.success(f"Que cette journée de Carême soit fructueuse, {user_email.split('@')[0]}!")


def main_app_flow():
    """Gère l'état de l'application (Connexion vs Contenu)."""
    
    # 1. Initialiser les variables de session
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'is_registering' not in st.session_state:
        st.session_state.is_registering = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
        
    # Vérification des données lors du lancement initial
    if df_users.empty and sheet_users:
        st.warning("⚠️ Attention : La base d'utilisateurs est vide. La première inscription va créer la première ligne de données dans votre feuille.")
    
    if df_careme.empty:
        st.warning("⚠️ La base de contenu du Carême est vide. Veuillez la remplir pour afficher les parcours.")


    # Si l'utilisateur est connecté
    if st.session_state.authenticated:
        # Affichage du contenu
        display_careme_content(st.session_state.user_email)
        
        # Barre latérale pour la déconnexion
        with st.sidebar:
            st.write(f"Connecté : **{st.session_state.user_email}**")
            if st.button("Déconnexion"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.rerun()

    # Si l'utilisateur est en mode inscription
    elif st.session_state.is_registering:
        register_ui()

    # Si l'utilisateur est déconnecté (mode par défaut)
    else:
        login_ui()
        

if __name__ == "__main__":
    main_app_flow()
