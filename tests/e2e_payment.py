"""Simple end-to-end test for payment flow.
Requires .env with SUPABASE_URL and SUPABASE_KEY set and the Supabase schema applied.
"""
import os
import random
import time
from database import db

TEST_TELEGRAM_ID = 999999999999


def run():
    # create or reset test user
    u = db.get_user(TEST_TELEGRAM_ID)
    if u:
        # reset saldo
        db.supabase.table('users').update({'saldo': 0.0, 'comissao': 0.0}).eq('telegram_id', TEST_TELEGRAM_ID).execute()
    else:
        db.get_or_create_user(TEST_TELEGRAM_ID, 'e2e_test')

    # register payment
    payment_id = f"testp_{int(time.time())}_{random.randint(1000,9999)}"
    valor = 15.0
    db.registrar_pagamento(TEST_TELEGRAM_ID, payment_id, valor, 'pending')
    pag = db.get_pagamento(payment_id)
    assert pag and float(pag['valor']) == valor and pag['status'] == 'pending'
    print('registered payment', payment_id)

    # simulate approval
    ok = db.aprovar_pagamento_se_pendente(payment_id)
    assert ok, 'aprovar_pagamento_se_pendente failed'
    print('approved via DB')

    # credit (the bot code uses update_saldo + pagar_comissao after approval)
    # simulate that by calling update_saldo and pagar_comissao (should mirror webhook)
    db.update_saldo(TEST_TELEGRAM_ID, valor)
    db.pagar_comissao(TEST_TELEGRAM_ID, valor)

    user = db.get_user(TEST_TELEGRAM_ID)
    assert user and float(user['saldo']) >= valor
    print('user saldo after credit:', user['saldo'])

    # cleanup: mark payment cancelled/removed
    db.cancelar_pagamento_db(payment_id)
    print('cleanup done')


if __name__ == '__main__':
    run()
