ALL_SECTORS = [
    "Airlines",
    "Airports",
    "Automotive",
    "Banking",
    "Chemicals",
    "Conglomerates",
    "Consumer",
    "Consumer Durables",
    "Defense",
    "Electronics",
    "Energy",
    "Financial Services",
    "Food",
    "Healthcare",
    "Holding",
    "Industrials",
    "Insurance",
    "Investment",
    "Machinery",
    "Materials",
    "Mining",
    "Real Estate",
    "Retail",
    "Sports",
    "Steel",
    "Technology",
    "Telecom",
    "Utilities",
]


def _rule(positive: list[str] | None = None, negative: list[str] | None = None) -> dict[str, list[str]]:
    return {
        "positive": positive or [],
        "negative": negative or [],
    }


SECTOR_RULES: dict[str, dict[str, dict[str, list[str]]]] = {
    "energy": {
        "Airlines": _rule(
            ["Bilet fiyatlama gucu korunursa maliyet etkisi kismen yonetilebilir"],
            [
                "Enerji maliyet soku operasyonel marjlari baskilayabilir",
                "Yakit giderlerindeki artis sektor risk primini yukseltebilir",
            ],
        ),
        "Airports": _rule(
            ["Yolcu talebi guclu kalirsa maliyet baskisinin bir kismi dengeleyebilir"],
            [
                "Enerji ve lojistik maliyet artisi terminal operasyon giderlerini yukseltebilir",
                "Hava yolu maliyet baskisi trafik beklentilerini zayiflatabilir",
            ],
        ),
        "Automotive": _rule(
            ["Fiyatlama disiplini korunursa enerji baskisinin bir kismi nihai fiyata yansitilabilir"],
            [
                "Enerji maliyet artisi uretim ve tedarik zinciri giderlerini yukseltebilir",
                "Akaryakit maliyeti talep tarafinda zayiflama yaratabilir",
            ],
        ),
        "Banking": _rule(
            ["Enerji sirketlerindeki gelir artisi kredi geri odeme kapasitesini destekleyebilir"],
            ["Enerji fiyat soku enflasyon ve faiz baskisini artirarak sektor carpani uzerinde baski yaratabilir"],
        ),
        "Chemicals": _rule(
            ["Urun fiyatlamasi desteklenirse spreadler gecici olarak guclenebilir"],
            [
                "Enerji ve petrokimya girdi maliyetleri marjlari baskilayabilir",
                "Gaz ve elektrik maliyetindeki artis uretim planlamasini zorlayabilir",
            ],
        ),
        "Conglomerates": _rule(
            ["Portfoy cesitliligi enerji soku etkisini kisim bazinda dengeleyebilir"],
            ["Enerji fiyat oynakligi holding sirketlerinde net aktif deger iskontosunu artirabilir"],
        ),
        "Consumer": _rule(
            ["Guclu marka fiyatlama gucu maliyet gecisini destekleyebilir"],
            [
                "Enerji ve lojistik maliyeti tuketim urunlerinde marj baskisi yaratabilir",
                "Hanehalki butcesindeki enerji payinin artisi talebi zayiflatabilir",
            ],
        ),
        "Consumer Durables": _rule(
            ["Ihracat ve kur destegi maliyet artisini kismen dengeleyebilir"],
            [
                "Enerji maliyetleri dayanikli tuketim uretiminde marj baskisi yaratabilir",
                "Tuketici talebi enerji faturasi baskisiyla yavaslayabilir",
            ],
        ),
        "Defense": _rule(
            ["Enerji ve jeopolitik gerilim savunma harcamalarini destekleyebilir"],
            ["Enerji maliyet artisi tedarik ve uretim planlamasini zorlayabilir"],
        ),
        "Electronics": _rule(
            ["Yuksek katma degerli urun karmasi maliyet soku etkisini sinirlayabilir"],
            [
                "Enerji maliyeti elektronik uretim giderlerini yukseltebilir",
                "Lojistik maliyetler ihracat teslim surelerini baskilayabilir",
            ],
        ),
        "Energy": _rule(
            [
                "Enerji ureticileri fiyatlama destegi bulabilir",
                "Yukselen enerji fiyatlari ciro ve operasyonel nakit akisina destek verebilir",
            ],
            ["Lojistik ve finansman maliyetlerindeki artis operasyonel oynakligi yukseltebilir"],
        ),
        "Financial Services": _rule(
            ["Enerji temali varlik hareketliligi finansal islemlerde hacim destegi saglayabilir"],
            ["Enerji soku risk primi ve finansman maliyetleri uzerinden sektor iskontosunu artirabilir"],
        ),
        "Food": _rule(
            ["Temel tuketim niteligindeki urunler talep dayanikliligini koruyabilir"],
            [
                "Enerji ve soguk zincir maliyetleri gida marjlarini baskilayabilir",
                "Nakliye maliyetleri dagitim verimliligini zayiflatabilir",
            ],
        ),
        "Healthcare": _rule(
            ["Savunmaci talep yapisi saglik sirketlerinde goreli dayaniklilik sunabilir"],
            ["Enerji ve ithal girdi maliyeti saglik operasyonlarinda marj baskisi yaratabilir"],
        ),
        "Holding": _rule(
            ["Cesitlendirilmis istirak yapisi enerji soku etkisini kismen dengeleyebilir"],
            ["Enerji fiyat oynakligi holding portfoyundeki sanayi sirketlerini baskilayabilir"],
        ),
        "Industrials": _rule(
            ["Proje bazli fiyat ayarlamalari maliyet baskisinin bir kismini telafi edebilir"],
            [
                "Enerji ve yakit maliyeti sanayi sirketlerinde marj daralmasi yaratabilir",
                "Lojistik baski teslimat takvimi ve siparis kalitesini bozabilir",
            ],
        ),
        "Insurance": _rule(
            ["Enflasyonist ortam nominal prim uretimini destekleyebilir"],
            ["Enerji soku enflasyon ve hasar maliyet beklentilerini yukseltebilir"],
        ),
        "Investment": _rule(
            ["Emtia temali varliklardaki deger artisi portfoy degerini destekleyebilir"],
            ["Enerji soku riskli varlik degerlemelerinde dalgalanmayi artirabilir"],
        ),
        "Machinery": _rule(
            ["Siparislerin doviz bazli olmasi marj baskisini kismen hafifletebilir"],
            ["Enerji ve metal maliyeti makina uretiminde marjlari zayiflatabilir"],
        ),
        "Materials": _rule(
            ["Baz emtia fiyatlamasi enerji soku ile destek bulabilir"],
            ["Enerji maliyetleri cimento, cam ve benzeri malzeme uretiminde gider baskisi yaratabilir"],
        ),
        "Mining": _rule(
            ["Emtia fiyatlarindaki yukselis madencilik gelirlerini destekleyebilir"],
            ["Enerji ve lojistik maliyetleri cevher cikarma ve sevkiyat giderlerini yukseltebilir"],
        ),
        "Real Estate": _rule(
            ["Enflasyon ortami kira guncellemeleri uzerinden gelirleri destekleyebilir"],
            ["Enerji maliyetleri AVM ve proje isletme giderlerini artirabilir"],
        ),
        "Retail": _rule(
            ["Temel tuketim segmentleri talep dayanikliligini koruyabilir"],
            [
                "Enerji ve dagitim maliyetleri perakende marjlarini baskilayabilir",
                "Akaryakit maliyeti tuketici trafik ve sepet buyuklugunu zayiflatabilir",
            ],
        ),
        "Sports": _rule(
            ["Yuksek taraftar ilgisi gelirleri kisa sureli destekleyebilir"],
            ["Enerji ve isletme maliyetleri zayif finansal yapili spor sirketlerinde baski yaratabilir"],
        ),
        "Steel": _rule([], ["Enerji maliyetleri uretim giderlerini yukseltebilir"]),
        "Technology": _rule(
            ["Yazilim agirlikli gelir yapisi enerji soku etkisini diger sanayi kollarina gore sinirlayabilir"],
            ["Veri merkezi ve donanim maliyetleri uzerinde enerji baskisi artabilir"],
        ),
        "Telecom": _rule(
            ["Duzenli nakit akisi enerji soku doneminde goreli dayaniklilik saglayabilir"],
            ["Enerji maliyetleri baz istasyonu ve altyapi giderlerini yukseltebilir"],
        ),
        "Utilities": _rule(
            [
                "Enerji tarifeleri ve fiyat gecisleri utility sirketlerinde gelir destegi saglayabilir",
                "Elektrik fiyat hareketi utility nakit akisini guclendirebilir",
            ],
            ["Regulasyon ve tavan fiyat mekanizmalari enerji avantajinin tam yansimasini sinirlayabilir"],
        ),
    },
    "geopolitics": {
        "Airlines": _rule([], ["Jeopolitik gerilim dis hat trafigi ve operasyonel planlamayi bozabilir"]),
        "Airports": _rule([], ["Jeopolitik gerilim yolcu akisi ve transit trafik beklentilerini zayiflatabilir"]),
        "Automotive": _rule([], ["Jeopolitik gerilim tedarik zinciri ve ihracat pazarlarinda aksama yaratabilir"]),
        "Banking": _rule(
            ["Guclu sermaye yapisina sahip bankalar volatil donemde goreli dayaniklilik gosterebilir"],
            ["Riskten kacinma davranisi bankacilik hisselerinde iskonto yaratabilir"],
        ),
        "Chemicals": _rule([], ["Jeopolitik gerilim petrokimya tedarigi ve lojistik akislari uzerinde baski yaratabilir"]),
        "Conglomerates": _rule([], ["Jeopolitik belirsizlik holding portfoylerinde iskonto oranini yukseltebilir"]),
        "Consumer": _rule([], ["Jeopolitik risk tuketici guvenini zayiflatip talebi yavaslatabilir"]),
        "Consumer Durables": _rule([], ["Jeopolitik gerilim ithal girdi ve dagitim kanallarinda risk yaratabilir"]),
        "Defense": _rule(
            ["Jeopolitik gerilim savunma talebi ve proje ilgisini artirabilir"],
            ["Uluslararasi tedarik zinciri baskisi proje takvimlerini zorlayabilir"],
        ),
        "Electronics": _rule([], ["Jeopolitik gerilim elektronik komponent tedariginde gecikme riski yaratabilir"]),
        "Energy": _rule(
            ["Jeopolitik gerilim enerji fiyatlarini destekleyerek sektor gelir beklentisini guclendirebilir"],
            ["Siyasi risk ve sevkiyat baskisi operasyonel oynakligi artirabilir"],
        ),
        "Financial Services": _rule([], ["Jeopolitik gerilim riskli varlik talebini zayiflatip finansal islemleri baskilayabilir"]),
        "Food": _rule([], ["Jeopolitik gerilim tarim emtia ve lojistik maliyetleri uzerinden gida sirketlerini baskilayabilir"]),
        "Healthcare": _rule(
            ["Savunmaci sektor yapisi volatil donemde goreli talep istikrari sunabilir"],
            ["Jeopolitik gerilim ithal tibbi girdi ve ekipman maliyetlerini artirabilir"],
        ),
        "Holding": _rule([], ["Jeopolitik risk holding sirketlerinin portfoy degerlemelerinde iskonto yaratabilir"]),
        "Industrials": _rule([], ["Jeopolitik gerilim proje teslimati ve sanayi lojistiginde aksama yaratabilir"]),
        "Insurance": _rule([], ["Jeopolitik gerilim hasar ve reasurans maliyet beklentilerini yukseltebilir"]),
        "Investment": _rule([], ["Jeopolitik oynaklik portfoy sirketlerinde degerleme baskisi yaratabilir"]),
        "Machinery": _rule([], ["Jeopolitik risk yedek parca ve komponent tedarigini zorlastirabilir"]),
        "Materials": _rule([], ["Jeopolitik gerilim baz malzeme lojistigi ve ihracat akisinda aksama yaratabilir"]),
        "Mining": _rule(
            ["Guvenli liman talebi belirli metal ve maden fiyatlamasina destek verebilir"],
            ["Jeopolitik risk maden ihracat rotalari ve operasyon guvenligini zorlayabilir"],
        ),
        "Real Estate": _rule([], ["Jeopolitik gerilim yatirim istahini zayiflatip gayrimenkul talebini baskilayabilir"]),
        "Retail": _rule([], ["Jeopolitik belirsizlik tuketici talebini ve magazalara trafik akisni zayiflatabilir"]),
        "Sports": _rule([], ["Jeopolitik gerginlik sponsorluk ve etkinlik gelir beklentilerini baskilayabilir"]),
        "Steel": _rule([], ["Bolgesel gerilim ihracat ve lojistik akisini bozabilir"]),
        "Technology": _rule([], ["Jeopolitik risk teknoloji tedarik zinciri ve proje kararliligini zayiflatabilir"]),
        "Telecom": _rule(
            ["Kritik altyapi niteligindeki operatorler volatil donemde goreli savunmaci algi kazanabilir"],
            ["Jeopolitik risk ekipman tedarigi ve sermaye harcamalari uzerinde baski yaratabilir"],
        ),
        "Utilities": _rule(
            ["Jeopolitik risk enerji altyapisina stratejik onem kazandirarak utility algisini destekleyebilir"],
            ["Bolgesel gerilim yakit tedarigi ve uretim planlamasini bozabilir"],
        ),
    },
    "rates": {
        "Airlines": _rule([], ["Faiz yukselisi finansman maliyetlerini artirabilir"]),
        "Airports": _rule([], ["Faiz yukselisi altyapi ve finansman giderlerini artirabilir"]),
        "Automotive": _rule([], ["Faiz yukselisi arac kredileri ve tuketici talebini zayiflatabilir"]),
        "Banking": _rule(
            ["Faiz ortami net faiz marjini desteklerse gelir tarafinda denge saglanabilir"],
            [
                "Faiz oynakligi kredi talebi ve aktif kalitesi beklentilerini bozabilir",
                "Regulasyon tartismalari sektor degerlemesini baskilayabilir",
            ],
        ),
        "Chemicals": _rule([], ["Faiz artisi isletme sermayesi ve yatirim maliyetlerini yukseltebilir"]),
        "Conglomerates": _rule([], ["Faiz yukselisi holding portfoyundeki borclu istiraklerin degerlemesini baskilayabilir"]),
        "Consumer": _rule([], ["Faiz yukselisi tuketici talebini ve fiyatlama gucunu zayiflatabilir"]),
        "Consumer Durables": _rule([], ["Faiz yukselisi dayanikli tuketim ve taksitli satis ivmesini baskilayabilir"]),
        "Defense": _rule(
            ["Kamu destekli uzun vadeli projeler faiz soku etkisini sinirlayabilir"],
            ["Fonlama maliyetlerindeki artis yeni proje finansmanini zorlayabilir"],
        ),
        "Electronics": _rule([], ["Faiz artisi tuketici elektroniği talebini zayiflatabilir"]),
        "Energy": _rule([], ["Faiz ve finansman maliyeti enerji projelerinde iskontoyu yukseltebilir"]),
        "Financial Services": _rule(
            ["Faiz hareketliligi leasing ve finansman spreadlerini destekleyebilir"],
            ["Fonlama maliyeti yukselisi islem hacmi ve aktif kaliteyi baskilayabilir"],
        ),
        "Food": _rule(["Temel tuketim niteliği faiz soku doneminde goreli dayaniklilik saglayabilir"], ["Faiz yukselisi maliyet finansmani ve tuketici talebi uzerinde baski yaratabilir"]),
        "Healthcare": _rule(["Savunmaci talep yapisi faiz oynakligina karsi goreli destek sunabilir"], ["Faiz ve kur baskisi ithal tibbi girdi maliyetlerini zorlayabilir"]),
        "Holding": _rule([], ["Faiz artisi iskonto oranlari uzerinden holding degerlemelerini baskilayabilir"]),
        "Industrials": _rule([], ["Faiz yukselisi proje finansmani ve sanayi siparis kalitesini zayiflatabilir"]),
        "Insurance": _rule(["Faiz artisi yatirim portfoyu gelirlerini destekleyebilir"], ["Piyasa oynakligi finansal varlik degerlemelerinde baski yaratabilir"]),
        "Investment": _rule([], ["Faiz artisi riskli varlik iskontosunu yukselterek portfoy degerini baskilayabilir"]),
        "Machinery": _rule([], ["Faiz artisi makina yatirimi talebini ve siparis istahini azaltabilir"]),
        "Materials": _rule([], ["Faiz ve talep baskisi baz malzeme siparislerini zayiflatabilir"]),
        "Mining": _rule([], ["Faiz yukselisi emtia talebini ve risk istahini zayiflatabilir"]),
        "Real Estate": _rule([], ["Faiz artisi konut ve ticari gayrimenkul talebini baskilayabilir"]),
        "Retail": _rule([], ["Faiz yukselisi tuketici finansman kosullarini zorlastirarak perakende talebini baskilayabilir"]),
        "Sports": _rule([], ["Faiz ve finansman maliyeti zayif bilancolu spor sirketlerinde baski yaratabilir"]),
        "Steel": _rule([], ["Faiz ve talep baskisi sanayi siparislerinde zayiflama yaratabilir"]),
        "Technology": _rule(["Net nakit pozisyonu guclu teknoloji sirketleri faiz oynakligina karsi goreli esneklik gosterebilir"], ["Faiz artisi buyume hisselerinde degerleme iskontosunu yukseltebilir"]),
        "Telecom": _rule(["Duzenli abonelik gelirleri faiz soku doneminde nakit akisi gorunurlugu saglayabilir"], ["Faiz artisi altyapi yatirimi ve borcluluk maliyetini yukseltebilir"]),
        "Utilities": _rule(["Defansif nakit akisi utility sirketlerinde faiz oynakligina karsi goreli dayaniklilik sunabilir"], ["Faiz artisi proje finansmani ve borcluluk maliyetini yukseltebilir"]),
    },
    "trade": {
        "Airlines": _rule([], ["Ticaret gerilimi kargo ve dis talep hacmini zayiflatabilir"]),
        "Airports": _rule([], ["Ticaret gerilimi uluslararasi yolcu ve kargo trafigini baskilayabilir"]),
        "Automotive": _rule([], ["Ticaret kisitlari ihracat akisi ve tedarik zincirinde aksama yaratabilir"]),
        "Banking": _rule([], ["Ticaret hacmindeki daralma kredi buyumesi beklentisini zayiflatabilir"]),
        "Chemicals": _rule([], ["Ticaret ve gumruk kisitlari kimyasal girdi maliyetlerini artirabilir"]),
        "Conglomerates": _rule([], ["Ticaret gerilimi cesitli ihracat ve sanayi istiraklerini baskilayabilir"]),
        "Consumer": _rule([], ["Ticaret baskisi tedarik maliyeti ve tuketici fiyatlamasi uzerinde baski yaratabilir"]),
        "Consumer Durables": _rule([], ["Gumruk ve ticaret engelleri dayanikli tuketim tedarik zincirini zorlayabilir"]),
        "Defense": _rule(
            ["Dis tedarik baskisi yerli savunma tedarikcilerine ilgiyi artirabilir"],
            ["Disa bagimli komponentler teslimat riskini yukseltebilir"],
        ),
        "Electronics": _rule([], ["Kuresel ticaret gerilimi elektronik komponent ve yariletken tedarigini zorlastirabilir"]),
        "Energy": _rule(["Emtia akisi degisimi belirli enerji oyunculari icin ticaret marji firsati yaratabilir"], ["Ticaret kisitlari enerji lojistigi ve ihracat rotalarini bozabilir"]),
        "Financial Services": _rule([], ["Ticaret hacmindeki zayiflama finansman ve leasing talebini azaltabilir"]),
        "Food": _rule([], ["Ticaret kisitlari tarim emtiasi ve girdi maliyetlerini yukseltebilir"]),
        "Healthcare": _rule([], ["Ticaret kisitlari tibbi ekipman ve ilac hammaddesi tedariğini zorlayabilir"]),
        "Holding": _rule([], ["Ticaret daralmasi holding portfoyundeki ihracatci sirketleri baskilayabilir"]),
        "Industrials": _rule([], ["Ticaret gerilimi sanayi siparis akisi ve ihracat teslimlerini zorlayabilir"]),
        "Insurance": _rule([], ["Ticaret hacmi daralmasi ticari sigorta ve kurumsal prim buyumesini yavaslatabilir"]),
        "Investment": _rule([], ["Ticaret baskisi portfoydeki ihracat ve emtia temali varliklarda oynakligi artirabilir"]),
        "Machinery": _rule([], ["Ticaret kisitlari makina ihracati ve yedek parca akisini zayiflatabilir"]),
        "Materials": _rule([], ["Ticaret gerilimi cam, cimento ve baz malzeme ihracatini zayiflatabilir"]),
        "Mining": _rule(["Arz darligi belirli metal ve maden fiyatlamasini destekleyebilir"], ["Ticaret kisitlari cevher ihracati ve lojistik akisi uzerinde baski yaratabilir"]),
        "Real Estate": _rule([], ["Ticaret yavaslamasi ticari gayrimenkul talebi ve yatirim istahini zayiflatabilir"]),
        "Retail": _rule([], ["Ithal urun maliyetleri ve tedarik zinciri baskisi perakende marjlarini zayiflatabilir"]),
        "Sports": _rule([], ["Ticaret ve sponsorluk daralmasi spor kulubu gelir kalemlerini baskilayabilir"]),
        "Steel": _rule(
            ["Arz daralmasi fiyatlama gucunu ve gelir beklentisini destekleyebilir"],
            ["Ticaret kisitlari girdi ve lojistik maliyetlerini artirabilir"],
        ),
        "Technology": _rule([], ["Ticaret gerilimi donanim, lisans ve teknoloji bileşeni tedarigini zorlayabilir"]),
        "Telecom": _rule([], ["Ticaret kisitlari telekom ekipmani ve altyapi yatirim takvimini baskilayabilir"]),
        "Utilities": _rule([], ["Ticaret ve tedarik baskisi enerji ekipmanlari ve bakim maliyetlerini artirabilir"]),
    },
}

REGION_RULES: dict[str, dict[str, dict[str, list[str]]]] = {
    "middle_east": {
        "Airlines": _rule([], ["Orta Dogu gerilimi ucus rotalari ve operasyonel planlamada ek baski yaratabilir"]),
        "Airports": _rule([], ["Orta Dogu kaynakli gerilim transit yolcu ve ucus trafik akisini zayiflatabilir"]),
        "Automotive": _rule([], ["Orta Dogu lojistik riski otomotiv sevkiyat ve tedarigini zorlayabilir"]),
        "Banking": _rule([], ["Orta Dogu kaynakli riskten kacinma akimi bankacilik hisselerinde baski yaratabilir"]),
        "Chemicals": _rule([], ["Orta Dogu kaynakli petrokimya ve enerji tedarik riski kimya sektorunu baskilayabilir"]),
        "Conglomerates": _rule([], ["Orta Dogu gerilimi bolgesel maruziyeti olan holdinglerde iskonto baskisi yaratabilir"]),
        "Consumer": _rule([], ["Bolgesel gerilim tedarik ve dagitim maliyetleri uzerinden tuketim sirketlerini baskilayabilir"]),
        "Consumer Durables": _rule([], ["Orta Dogu kaynakli lojistik riski ithal parca ve dagitim akisini zorlayabilir"]),
        "Defense": _rule(["Orta Dogu guvenlik gundemi savunma talep algisini guclendirebilir"], []),
        "Electronics": _rule([], ["Bolgesel lojistik riski elektronik tedarik surelerini uzatabilir"]),
        "Energy": _rule(["Orta Dogu gerilimi enerji fiyatlarini destekleyerek sektor gelir beklentisini guclendirebilir"], ["Sevkiyat ve tedarik zinciri baskisi enerji operasyonlarinda oynakligi artirabilir"]),
        "Financial Services": _rule([], ["Orta Dogu kaynakli riskten kacinma finansman islem hacimlerini baskilayabilir"]),
        "Food": _rule([], ["Bolgesel lojistik riski gida hammadde ve sevkiyat maliyetlerini yukseltebilir"]),
        "Healthcare": _rule([], ["Orta Dogu kaynakli lojistik ve ithal girdi baskisi saglik sektorunu zorlayabilir"]),
        "Holding": _rule([], ["Bolgesel gerilim holding portfoyundeki ticaret ve enerji maruziyetini baskilayabilir"]),
        "Industrials": _rule([], ["Bolgesel lojistik riski sanayi sirketlerinde teslimat ve proje akisini zorlayabilir"]),
        "Insurance": _rule([], ["Bolgesel gerilim reasurans ve ticari risk primlerini yukseltebilir"]),
        "Investment": _rule([], ["Orta Dogu kaynakli riskten kacinma portfoy degerlemelerini baskilayabilir"]),
        "Machinery": _rule([], ["Bolgesel lojistik ve tedarik baskisi makina sevkiyat takvimlerini zorlayabilir"]),
        "Materials": _rule([], ["Bolgesel enerji ve lojistik riski baz malzeme maliyetlerini yukseltebilir"]),
        "Mining": _rule([], ["Bolgesel lojistik riski maden sevkiyati ve hammadde akisinda baski yaratabilir"]),
        "Real Estate": _rule([], ["Bolgesel risk istahi zayifligi gayrimenkul yatirim talebini baskilayabilir"]),
        "Retail": _rule([], ["Bolgesel lojistik riski perakende tedarik zincirini ve maliyet yapisini zayiflatabilir"]),
        "Sports": _rule([], ["Bolgesel gerilim sponsorluk ve uluslararasi etkinlik gelirlerini baskilayabilir"]),
        "Steel": _rule([], ["Bolgesel lojistik riski hammadde ve sevkiyat akisini zorlayabilir"]),
        "Technology": _rule([], ["Bolgesel gerilim veri, altyapi ve tedarik surecleri uzerinde baski yaratabilir"]),
        "Telecom": _rule([], ["Bolgesel gerilim altyapi ve ekipman tedarik zinciri uzerinde baski yaratabilir"]),
        "Utilities": _rule(["Bolgesel enerji gerilimi utility sektorunde stratejik onem algisini guclendirebilir"], ["Bolgesel gerilim yakit tedarigi ve uretim planlamasini zorlayabilir"]),
    },
    "global": {
        "Airlines": _rule(["Kuresel talep dengesi korunursa trafik tarafinda destek surer"], ["Kuresel risk istahi zayiflarsa yolcu ve kargo beklentileri bozulabilir"]),
        "Airports": _rule(["Kuresel seyahat talebi guclu kalirsa terminal gelirleri desteklenebilir"], ["Kuresel risk istahi zayiflarsa yolcu ve transfer trafigi zayiflayabilir"]),
        "Automotive": _rule(["Kuresel talep toparlanmasi ihracat siparislerini destekleyebilir"], ["Kuresel talep zayifligi otomotiv siparis ve fiyatlamasini baskilayabilir"]),
        "Banking": _rule(["Kuresel likidite rahatlarsa banka carpani toparlanabilir"], ["Kuresel faiz ve risk primi baskisi bankacilik degerlemesini zayiflatabilir"]),
        "Chemicals": _rule(["Kuresel emtia dongusu toparlanirsa kimya urunlerine talep desteklenebilir"], ["Kuresel sanayi yavaslamasi kimyasal talep ve marjlari baskilayabilir"]),
        "Conglomerates": _rule(["Kuresel risk istahi toparlanirsa holding iskontolari daralabilir"], ["Kuresel oynaklik holding portfoy degerlemelerinde baski yaratabilir"]),
        "Consumer": _rule(["Kuresel tuketim egilimi guclu kalirsa ihracat ve fiyatlama gucu desteklenebilir"], ["Kuresel talep zayifligi tuketim urunlerinde siparis ve marji baskilayabilir"]),
        "Consumer Durables": _rule(["Kuresel talep toparlanmasi beyaz esya ve dayanikli tuketim ihracatini destekleyebilir"], ["Kuresel talep zayifligi siparis ve kapasite kullanimini baskilayabilir"]),
        "Defense": _rule(["Kuresel guvenlik gundemi savunma projelerine ilgiyi artirabilir"], []),
        "Electronics": _rule(["Kuresel teknoloji talebi guclu kalirsa elektronik ihracati desteklenebilir"], ["Kuresel yavaslama elektronik siparislerini baskilayabilir"]),
        "Energy": _rule(["Kuresel enerji fiyat dengesi ve talep artisi sektor gelirlerini destekleyebilir"], ["Kuresel talep zayifligi enerji fiyatlarinda baski yaratabilir"]),
        "Financial Services": _rule(["Kuresel risk istahi toparlanirsa finansal islem hacimleri canlanabilir"], ["Kuresel oynaklik finansman islem hacimleri ve portfoy degerlemelerini baskilayabilir"]),
        "Food": _rule(["Temel tuketim dogasi gida sektorunde kuresel yavaslamaya karsi goreli dayaniklilik sunabilir"], ["Kuresel emtia ve lojistik baskisi gida marjlarini zayiflatabilir"]),
        "Healthcare": _rule(["Savunmaci sektor yapisi kuresel dalgalanma doneminde goreli destek sunabilir"], ["Kuresel finansman ve ithal girdi baskisi saglik marjlarini zorlayabilir"]),
        "Holding": _rule(["Kuresel risk istahi toparlanirsa holding iskontolari daralabilir"], ["Kuresel riskten kacinma holding degerlemelerinde baski yaratabilir"]),
        "Industrials": _rule(["Kuresel talep dengesi sanayi siparis akisini destekleyebilir"], ["Kuresel yavaslama proje akisi ve siparis kalitesini bozabilir"]),
        "Insurance": _rule(["Kuresel tahvil getirileri yatirim portfoyu gelirlerini destekleyebilir"], ["Kuresel piyasa oynakligi finansal varlik degerlerini baskilayabilir"]),
        "Investment": _rule(["Kuresel risk istahi toparlanirsa portfoy degerlemeleri desteklenebilir"], ["Kuresel riskten kacinma portfoy degerlemelerinde indirim yaratabilir"]),
        "Machinery": _rule(["Kuresel yatirim dongusu guclenirse makina talebi canlanabilir"], ["Kuresel yavaslama makina siparis ve sevkiyatlarini baskilayabilir"]),
        "Materials": _rule(["Kuresel altyapi ve sanayi talebi baz malzeme fiyatlamasini destekleyebilir"], ["Kuresel talep zayifligi baz malzeme hacim ve fiyatlarini baskilayabilir"]),
        "Mining": _rule(["Kuresel arz sikisiligi ve emtia talebi madencilik fiyatlamasini destekleyebilir"], ["Kuresel talep zayifligi maden fiyatlarini baskilayabilir"]),
        "Real Estate": _rule(["Kuresel likidite rahatlamasi gayrimenkul ilgisini destekleyebilir"], ["Kuresel faiz ve risk primi baskisi gayrimenkul degerlemelerini zayiflatabilir"]),
        "Retail": _rule(["Kuresel tuketim gorunumu guclu kalirsa perakende talebi desteklenebilir"], ["Kuresel talep zayifligi ve maliyet baskisi perakende marjlarini zayiflatabilir"]),
        "Sports": _rule(["Kuresel medya ve sponsorluk ilgisi gelir akisini destekleyebilir"], ["Kuresel riskten kacinma sponsorluk ve ticari gelir beklentilerini baskilayabilir"]),
        "Steel": _rule(["Kuresel arz sikisiligi fiyatlama ortaminda destek saglayabilir"], ["Kuresel talep zayifligi sanayi metal fiyatlamasini baskilayabilir"]),
        "Technology": _rule(["Kuresel dijitallesme talebi teknoloji gelirlerini destekleyebilir"], ["Kuresel riskten kacinma buyume carpani ve teknoloji yatirimlarini baskilayabilir"]),
        "Telecom": _rule(["Duzenli servis gelirleri kuresel oynaklikta goreli savunmaci profil sunabilir"], ["Kuresel ekipman ve finansman maliyeti baskisi yatirim planlarini zorlayabilir"]),
        "Utilities": _rule(["Savunmaci nakit akisi utility sektorunde kuresel oynaklikta goreli destek sunabilir"], ["Kuresel emtia ve finansman maliyeti utility marjlarini baskilayabilir"]),
    },
}

TICKER_OVERRIDES: dict[str, dict[str, dict[str, list[str]]]] = {
    "THYAO": {
        "energy": {
            "positive": [
                "Kur ve bilet optimizasyonu ile yakit baskisinin bir kismi dengelenebilir",
            ],
            "negative": [
                "Jet yakiti maliyet soku THYAO icin sektor ortalamasindan daha belirgin etki yaratabilir",
            ],
        }
    },
    "PGSUS": {
        "energy": {
            "positive": [
                "Yardimci gelir kalemleri maliyet baskisinin bir kismini dengeleyebilir",
            ],
            "negative": [
                "Jet yakiti maliyet soku PGSUS marjlari uzerinde dogrudan baski yaratabilir",
            ],
        }
    },
    "TAVHL": {
        "geopolitics": {
            "positive": [],
            "negative": [
                "Transit trafik ve duty-free gelirleri jeopolitik gerilimde daha hizli zayiflayabilir",
            ],
        }
    },
    "ASELS": {
        "geopolitics": {
            "positive": [
                "Bolgesel guvenlik gundemi ASELS proje gorunurlugunu guclendirebilir",
            ],
            "negative": [],
        }
    },
    "GARAN": {
        "rates": {
            "positive": [
                "Guclu mevduat tabani faiz oynakligi doneminde goreli esneklik saglayabilir",
            ],
            "negative": [
                "Bankacilikta regule marj baskisi GARAN icin fiyatlamayi zayiflatabilir",
            ],
        }
    },
    "EREGL": {
        "trade": {
            "positive": [
                "Metal arz daralmasi EREGL icin fiyatlama gucunu sektor ortalamasindan fazla destekleyebilir",
            ],
            "negative": [],
        }
    },
    "TUPRS": {
        "energy": {
            "positive": [
                "Rafineri urun fiyatlama ortami TUPRS marjlarini destekleyebilir",
            ],
            "negative": [
                "Ham petrol ve tasima maliyetindeki oynaklik rafineri marjlarinda dalgalanma yaratabilir",
            ],
        }
    },
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def derive_impacts(
    ticker: str,
    sector: str | None,
    event_category: str | None,
    region: str | None,
) -> tuple[list[str], list[str]]:
    normalized_ticker = ticker.upper()
    normalized_category = (event_category or "").lower()
    normalized_region = (region or "").lower()
    positive: list[str] = []
    negative: list[str] = []

    if sector is not None:
        sector_rules = SECTOR_RULES.get(normalized_category, {}).get(sector, {})
        positive.extend(sector_rules.get("positive", []))
        negative.extend(sector_rules.get("negative", []))

        # De-escalation events should not inherit generic regional tension risks.
        # Example: a US-Iran peace/Hormuz reopening headline is Middle East related,
        # but its market effect is risk-premium relief rather than fresh conflict pressure.
        if "deescalation" not in normalized_category and "de_escalation" not in normalized_category:
            region_rules = REGION_RULES.get(normalized_region, {}).get(sector, {})
            positive.extend(region_rules.get("positive", []))
            negative.extend(region_rules.get("negative", []))

    ticker_rules = TICKER_OVERRIDES.get(normalized_ticker, {}).get(normalized_category, {})
    positive.extend(ticker_rules.get("positive", []))
    negative.extend(ticker_rules.get("negative", []))

    return _dedupe(positive), _dedupe(negative)
