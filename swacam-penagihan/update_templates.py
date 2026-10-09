from sqlalchemy import create_engine, text
from config import DATABASE_URL
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    tpl_ramah = """Yth. Bapak/Ibu Pelanggan PLN, {nama} dengan ID Pelanggan {idpel}.

Sebagai bentuk pelayanan terbaik, kami mengingatkan bahwa periode pembayaran tagihan listrik berlangsung setiap tanggal 2 hingga tanggal 20 setiap bulan.

Kami menghimbau Bapak/Ibu untuk melakukan pembayaran sebelum tanggal 20 melalui kanal pembayaran resmi seperti PLN Mobile maupun gerai pembayaran lainnya.

Apabila hingga melewati tanggal 20 tagihan listrik belum diselesaikan, maka sesuai ketentuan yang berlaku akan dilakukan pemutusan sementara aliran listrik sampai dengan kewajiban pembayaran dipenuhi.

Terima kasih atas perhatian dan kerja sama Bapak/Ibu dalam menjaga kelancaran pelayanan kelistrikan.

Salam hormat,
PT PLN (Persero) UID S2JB."""

    tpl_lewat = """Yth. Bapak/Ibu Pelanggan PLN, {nama} ID PEL. {idpel}.

Sebagai bentuk pelayanan terbaik, kami mengingatkan bahwa periode pembayaran tagihan listrik berlangsung setiap tanggal 2 hingga tanggal 20 setiap bulan.

Kami menghimbau Bapak/Ibu untuk melakukan pembayaran sebelum tanggal 20 melalui kanal pembayaran resmi seperti PLN Mobile maupun gerai pembayaran lainnya.

Bapak Ibu Yth, kami informasikan bahwa hari ini telah memasuki tanggal 21 akan tetapi tagihan listrik belum diselesaikan, maka sesuai ketentuan yang berlaku akan dilakukan pemutusan sementara aliran listrik sampai dengan kewajiban pembayaran dipenuhi.

Kami mengharapkan Bapak/Ibu mempunyai back up kelistrikan cadangan seperti genset dan lain-lain.

Terima kasih atas perhatian dan kerja sama Bapak/Ibu dalam menjaga kelancaran pelayanan kelistrikan.

Salam hormat,
PT PLN (Persero) UID S2JB."""

    conn.execute(text('UPDATE wa_template SET isi = :isi WHERE kode = "PENGINGAT_RAMAH"'), {'isi': tpl_ramah})
    conn.execute(text('UPDATE wa_template SET isi = :isi WHERE kode = "PENGINGAT_1"'), {'isi': tpl_lewat})
    conn.commit()
print('Templates in database updated successfully!')
