import sqlite3
import os

# Script para limpar o cliente travado no banco SQLite local da Speedy Cell
def rodar_limpeza():
    arquivo_banco = None
    for arquivo in os.listdir('.'):
        if arquivo.endswith('.db') or arquivo.endswith('.sqlite'):
            arquivo_banco = arquivo
            break
            
    if not arquivo_banco:
        print("❌ Arquivo de banco de dados (.db) não encontrado na pasta atual.")
        return

    print(f"🔍 Banco de dados encontrado: {arquivo_banco}")
    conn = sqlite3.connect(arquivo_banco)
    cursor = conn.cursor()

    whatsapp_travado = input("Digite o WhatsApp do cliente para remover do banco (somente números): ").strip()
    if not whatsapp_travado:
        print("Operação cancelada.")
        return

    try:
        cursor.execute("DELETE FROM Clientes WHERE WhatsApp = ?", (whatsapp_travado,))
        cursor.execute("DELETE FROM FluxoCaixa WHERE IdCliente IN (SELECT IdCliente FROM Clientes WHERE WhatsApp = ?)", (whatsapp_travado,))
        
        conn.commit()
        print(f"✨ SUCESSO: Os registros vinculados ao WhatsApp {whatsapp_travado} foram limpos com sucesso!")
        print("👉 Pode voltar ao sistema, dar um F5 e utilizá-lo normalmente.")
        
    except Exception as e:
        print(f"❌ Erro ao executar a limpeza: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    rodar_limpeza()
