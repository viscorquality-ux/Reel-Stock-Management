from app import app, db  # ඔබේ Main Flask ෆයිල් එක app.py නම් පමණක් මෙය භාවිතා කරන්න

def clear_other_tables():
    with app.app_context():
        # මකා නොදැමිය යුතු (සුරක්ෂිත කළ යුතු) Tables වල නම් මෙහි ඇතුළත් කරන්න.
        # සැලකිය යුතුයි: මෙහි යෙදිය යුත්තේ Model එකේ නම නොව, Database Table එකේ නමයි.
        # උදා: 'customer_product', 'active_stock'
        tables_to_keep = ['customer_product', 'active_stock'] 
        
        try:
            # Foreign Key ගැටළු මඟහරවා ගනිමින් අනුක්‍රමිකව tables වල data delete කිරීම
            for table in reversed(db.metadata.sorted_tables):
                if table.name not in tables_to_keep:
                    print(f"Clearing data from table: {table.name}...")
                    db.session.execute(table.delete())
            
            db.session.commit()
            print("\n✅ Successfully cleared temporary data from other tables!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error occurred: {e}")

if __name__ == '__main__':
    # මෙය Run කිරීමට පෙර Database එකේ Backup එකක් ලබා ගන්න
    confirm = input("Are you sure you want to delete data? (y/n): ")
    if confirm.lower() == 'y':
        clear_other_tables()
    else:
        print("Operation cancelled.")
