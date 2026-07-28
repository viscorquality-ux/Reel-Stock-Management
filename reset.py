from app import app, db
from sqlalchemy import text

def clear_data():
    with app.app_context():
        try:
            # Foreign keys තාවකාලිකව අක්‍රිය කිරීම (SQLite සඳහා)
            db.session.execute(text('PRAGMA foreign_keys = OFF;'))
            
            # මකා දැමිය යුතු Tables වල නම් මෙහි පහතින් දක්වා ඇත
            # ඔබේ Database එකේ ProgrammePlan සහ ReelHistory tables වල සැබෑ නම් මෙහි යොදන්න
            # බොහෝවිට ඒවායේ නම් programme_plan සහ reel_history වේ
            
            tables_to_clear = [
                'programme_plan',
                'reel_history'
                # තවත් tables ඇත්නම් මෙහි එකතු කරන්න (උදා: 'user_logs')
            ]
            
            for table in tables_to_clear:
                print(f"Clearing {table}...")
                db.session.execute(text(f'DELETE FROM {table}'))
            
            db.session.commit()
            
            # Foreign keys නැවත සක්‍රිය කිරීම
            db.session.execute(text('PRAGMA foreign_keys = ON;'))
            
            print("\n✅ Data cleared successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error occurred: {e}")

if __name__ == '__main__':
    clear_data()
