"""BIST/MKK uye kodu -> unvan eslemesi.

Kaynak: MKK'nin herkese acik "Araci Kurum Uye Listesi" (Duyuru 1686 Ek-3):
https://www.mkk.com.tr/tr-tr/Duyurular/Documents/Duyuru%201686%20Ek-3.xlsx

Matriks trade-flow akisindaki uye kodlarinin (bkz. trade_message.py,
alici_member_code/satici_member_code) buyuk cogunlugu bu listeyle birebir
eslesiyor - canli veriyle capraz dogrulandi (orn. YKR->Yapi Kredi Yatirim,
DZY->Deniz Yatirim, ZRY->Ziraat Yatirim, AKM->Ak Yatirim). Listede olmayan
bir kod gorulursen (yeni uye, yeniden adlandirma, borsa-disi katilimci vb.),
resolve_member_name() ham kodu oldugu gibi dondurur.
"""
from __future__ import annotations

MEMBER_CODE_TO_NAME: dict[str, str] = {
    "ACA": "Acar Menkul Değerler A.Ş.",
    "ACP": "A1 Capital Yatırım Menkul Değerler A.Ş.",
    "ADY": "Anadolu Yatırım Menkul Kıymetler A.Ş.",
    "AKM": "Ak Yatırım Menkul Değerler A.Ş.",
    "ALM": "Alb Menkul Değerler A.Ş.",
    "ALN": "Alan Yatırım Menkul Değerler A.Ş.",
    "AMK": "Alternatif Yatırım Menkul Değerler A.Ş.",
    "ANC": "Alnus Yatırım Menkul Değerler A.Ş.",
    "ATA": "Ata Yatırım Menkul Kıymetler A.Ş.",
    "AYX": "Ahlatcı Yatırım Menkul Değerler A.Ş.",
    "BAH": "Bahar Menkul Değerler Ticareti A.Ş.",
    "BGC": "BGC Partners Menkul Değerler A.Ş.",
    "BMK": "Bizim Menkul Değerler A.Ş.",
    "CIM": "Citi Menkul Değerler A.Ş.",
    "CSM": "Credit Suisse İstanbul Menkul Değerler A.Ş.",
    "DET": "Delta Menkul Değerler A.Ş.",
    "DMK": "Dinamik Menkul Değerler A.Ş.",
    "DSI": "Deutsche Securities Menkul Değerler A.Ş.",
    "DZY": "Deniz Yatırım Menkul Kıymetler A.Ş.",
    "EFG": "Burgan Yatırım Menkul Değerler A.Ş.",
    "FNY": "QNB Finans Yatırım Menkul Değerler A.Ş.",
    "GCM": "GCM Yatırım Menkul Değerler A.Ş.",
    "GDK": "Gedik Yatırım Menkul Değerler A.Ş.",
    "GLB": "Global Menkul Değerler A.Ş.",
    "GNI": "ING Menkul Değerler A.Ş.",
    "GRM": "Garanti Yatırım Menkul Kıymetler A.Ş.",
    "HLY": "Halk Yatırım Menkul Değerler A.Ş.",
    "HSY": "HSBC Yatırım Menkul Değerler A.Ş.",
    "IAZ": "Invest AZ Yatırım Menkul Değerler A.Ş.",
    "ICT": "ICBC Turkey Yatırım Menkul Değerler A.Ş.",
    "IKN": "Ikon Menkul Değerler A.Ş.",
    "IME": "Işık Menkul Değerler A.Ş.",
    "INM": "İntegral Yatırım Menkul Değerler A.Ş.",
    "IYF": "İnfo Yatırım Menkul Değerler A.Ş.",
    "IYM": "İş Yatırım Menkul Değerler A.Ş.",
    "MRS": "Marbaş Menkul Değerler A.Ş.",
    "MSA": "Meksa Yatırım Menkul Değerler A.Ş.",
    "MSI": "Morgan Stanley Menkul Değerler A.Ş.",
    "MTY": "Metro Yatırım Menkul Değerler A.Ş.",
    "NOR": "Noor Capital Market Menkul Değerler A.Ş.",
    "NTA": "Neta Menkul Değerler A.Ş.",
    "OMD": "Osmanlı Yatırım Menkul Değerler A.Ş.",
    "OYA": "Oyak Yatırım Menkul Değerler A.Ş.",
    "PAY": "Pay Menkul Değerler A.Ş.",
    "PHC": "PhillipCapital Menkul Değerler A.Ş.",
    "PIT": "Piramit Menkul Kıymetler A.Ş.",
    "PMK": "Prim Menkul Değerler A.Ş.",
    "POL": "Polen Menkul Değerler A.Ş.",
    "RKM": "Reel Kapital Menkul Değerler A.Ş.",
    "SKY": "Şeker Yatırım Menkul Değerler A.Ş.",
    "SNK": "Sanko Yatırım Menkul Değerler A.Ş.",
    "STJ": "Strateji Menkul Değerler A.Ş.",
    "TAC": "Tacirler Yatırım Menkul Değerler A.Ş.",
    "TBY": "TEB Yatırım Menkul Değerler A.Ş.",
    "TKY": "Turkish Yatırım Menkul Değerler A.Ş.",
    "TRA": "Tera Yatırım Menkul Değerler A.Ş.",
    "UNS": "Ünlü Menkul Değerler A.Ş.",
    "VKY": "Vakıf Yatırım Menkul Değerler A.Ş.",
    "VNB": "Venbey Yatırım Menkul Değerler A.Ş.",
    "YAT": "Yatırım Finansman Menkul Değerler A.Ş.",
    "YKR": "Yapı Kredi Yatırım Menkul Değerler A.Ş.",
    "ZRY": "Ziraat Yatırım Menkul Değerler A.Ş.",
}


def resolve_member_name(code: str) -> str:
    normalized = code.strip().upper()
    return MEMBER_CODE_TO_NAME.get(normalized, normalized)
