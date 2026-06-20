from fastapi import APIRouter, UploadFile, File, HTTPException, status
import pandas as pd
import io
from app.database import get_db_connection

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

@router.post("/upload-csv")
async def upload_inventory_csv(file: UploadFile = File(...)):
    # 1. Validate file extension type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid file format. Please upload a valid CSV file."
        )
    
    try:
        # 2. Read the file contents into memory using Pandas
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Strip any accidental whitespace from columns
        df.columns = [c.strip() for c in df.columns]
        
        # Expected column format checks
        required_columns = ['product_name', 'generic_name', 'category', 'batch_number', 'quantity', 'cost_price', 'retail_price', 'expiry_date']
        for col in required_columns:
            if col not in df.columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required data column: '{col}'"
                )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        records_imported = 0
        
        # 3. Stream data row by row safely into Postgres
        for _, row in df.iterrows():
            # Check if product exists, if not insert it
            cursor.execute(
                "SELECT id FROM \"Product\" WHERE name = %s LIMIT 1;", 
                (row['product_name'],)
            )
            product = cursor.fetchone()
            
            if product:
                product_id = product['id']
            else:
                cursor.execute(
                    "INSERT INTO \"Product\" (id, name, \"genericName\", category) VALUES (gen_random_uuid(), %s, %s, %s) RETURNING id;",
                    (row['product_name'], row['generic_name'], row['category'])
                )
                product_id = cursor.fetchone()['id']
            
            # Insert the unique supplier metadata if missing (Using a placeholder for initial onboarding)
            cursor.execute("SELECT id FROM \"Supplier\" LIMIT 1;")
            supplier = cursor.fetchone()
            if supplier:
                supplier_id = supplier['id']
            else:
                cursor.execute("INSERT INTO \"Supplier\" (id, name) VALUES (gen_random_uuid(), 'Default Supplier') RETURNING id;")
                supplier_id = cursor.fetchone()['id']
                
            # Insert the specific batch info linked to this product entry
            cursor.execute(
                """INSERT INTO \"Batch\" (id, \"batchNumber\", \"productId\", \"supplierId\", quantity, \"costPrice\", \"retailPrice\", \"expiryDate\") 
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'));""",
                (str(row['batch_number']), product_id, supplier_id, int(row['quantity']), float(row['cost_price']), float(row['retail_price']), str(row['expiry_date']))
            )
            records_imported += 1
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "success", "message": f"Successfully processed and stored {records_imported} batch items."}
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))