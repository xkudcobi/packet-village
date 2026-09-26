"""Every sentence the user can see, in English and Turkish.

Keep both tables in step: tests check that they share the same keys and
the same {placeholders}.
"""

EN = {
  # general
  "app_title": "Packet Village",
  "app_tagline": "Watch a message travel through a tiny internet, envelope by envelope.",
  "router_label": "Post {tag}",
  "unknown_place": "somewhere",

  # scenarios
  "sc_village": "Little village",
  "sc_village_blurb": "Six houses, five post offices and more than one way around.",
  "sc_bridges": "Two hills",
  "sc_bridges_blurb": "Two neighbourhoods joined by a narrow bridge and a long detour.",
  "sc_ring": "Round town",
  "sc_ring_blurb": "Post offices in a circle. Cut one cable and mail goes the long way.",
  "sc_grid": "Busy city",
  "sc_grid_blurb": "A grid of streets with many equally good routes.",
  "sc_random": "Random town",
  "sc_loaded": "Town from file",

  # demo letters
  "demo_1": "Hello from the other side of the village!",
  "demo_2": "Every envelope finds its own way home.",
  "demo_3": "Try cutting a cable while I am on the road.",
  "demo_4": "Big letters travel in many small pieces.",

  # events
  "ev_sent": "{src} sent a letter to {dst}, cut into {pieces} envelopes.",
  "ev_delivered": "{dst} got the whole letter from {src} in {ticks} steps.",
  "ev_failed": "{src} gave up: the letter to {dst} could not get through.",
  "ev_resend": "No thank-you note for envelope {num} yet, so it is sent again.",
  "ev_drop_queue": "Envelope {num} was thrown away at {node}: the shelf was full.",
  "ev_drop_noise": "Envelope {num} got soaked on the way to {node} and could not be read.",
  "ev_drop_no_route": "Envelope {num} got stuck at {node}: nobody there knew the way.",
  "ev_drop_ttl": "Envelope {num} wandered around too long and was retired at {node}.",
  "ev_drop_cut": "Envelope {num} fell off a cut cable near {node}.",
  "ev_cut": "Snip! The cable between {a} and {b} is cut. Envelopes lost with it: {lost}.",
  "ev_repair": "The cable between {a} and {b} works again.",
  "ev_settled": "After {rounds} rounds of passing news along, every post office has a fresh map.",

  # errors
  "err_unknown_house": "Please pick both a sender and a receiver.",
  "err_same_house": "The sender and the receiver must be two different houses.",
  "err_empty_message": "Write something first.",
  "err_no_cable": "There is no cable there.",
  "err_file_read": "Could not read the file: {detail}",
  "err_file_write": "Could not save the file: {detail}",
  "err_file_json": "This file is not a town file (broken JSON on line {line}).",
  "err_file_format": "This file is not a Packet Village town.",
  "err_file_version": "This town was saved by a newer version (format {version}).",
  "err_file_town": "The town in this file does not make sense: {detail}",
  "err_file_empty": "This town has fewer than two houses, so nobody could send a letter.",

  # window: top bar
  "lbl_town": "Town:",
  "btn_random": "New random town",
  "btn_open": "Open…",
  "btn_save": "Save…",
  "btn_pause": "Pause",
  "btn_play": "Play",

  # window: sending
  "sec_send": "Send a letter",
  "lbl_from": "From",
  "lbl_to": "To",
  "btn_send": "Send",

  # window: progress
  "sec_progress": "On its way",
  "progress_idle": "No letter on the road yet.",
  "progress_moving": "{got} of {total} envelopes have arrived",
  "progress_done": "Delivered in {ticks} steps!",
  "progress_failed": "It could not get through. Fix a cable and try again.",

  # window: knobs
  "sec_controls": "Knobs",
  "lbl_speed": "Speed",
  "lbl_chatter": "Busy streets",
  "lbl_noise": "Stormy weather",
  "lbl_queue": "Shelf size",
  "lbl_chunk": "Letters per envelope",
  "chk_way": "Show the way",
  "btn_repair": "Fix all cables",

  # window: counters
  "sec_stats": "Counters",
  "st_step": "Step",
  "st_sent": "Envelopes sent",
  "st_arrived": "Arrived",
  "st_lost": "Lost",
  "st_resent": "Sent again",
  "st_letters": "Letters delivered",
  "st_trip": "Average trip",
  "st_steps": "{n} steps",
  "st_none": "–",

  # window: inspector
  "sec_inspect": "Take a closer look",
  "inspect_hint": "Click a house or a post office to see what it knows.",
  "inspect_house": "{name} is a house.",
  "inspect_router": "{name} is a post office.",
  "inspect_cables": "Working cables: {up} of {count}",
  "inspect_waiting": "waiting on its shelves: {count}",
  "inspect_knows": "Which way to each house:",
  "inspect_route": "{dest}: via {hop} (cost {cost})",
  "inspect_noroute": "{dest}: no idea yet",

  # window: story and hints
  "sec_story": "What just happened",
  "hint_bar": "Click a cable to cut it, click it again to fix it. Drag houses and post offices around.",
  "status_healing": "The post offices are redrawing their maps…",
  "status_settled": "Every post office knows the way.",
  "legend_data": "piece of the letter",
  "legend_ack": "thank-you note",
  "legend_other": "other people's mail",
  "legend_cut": "cut cable",

  # dialogs
  "dlg_open_title": "Open a town",
  "dlg_save_title": "Save this town",
  "dlg_error_title": "Something went wrong",
  "file_type": "Town files",
  "file_all": "All files",

  # command line
  "cli_description": "Packet Village: watch a message cross a tiny internet. Without options it opens a window.",
  "cli_usage": "usage: ",
  "cli_options": "options",
  "cli_help_help": "show this help and exit",
  "cli_help_lang": "language for all text (tr or en)",
  "cli_help_headless": "run in the terminal instead of opening a window",
  "cli_help_list": "list the built-in towns and exit",
  "cli_help_scenario": "which town to use",
  "cli_help_from": "name of the sending house",
  "cli_help_to": "name of the receiving house",
  "cli_help_message": "the letter to send",
  "cli_help_ticks": "give up after this many steps",
  "cli_help_seed": "random seed, for repeatable runs",
  "cli_help_cut": "cut a cable before sending, e.g. A-B (may repeat)",
  "cli_help_chatter": "how busy the streets are, from 0 to 1",
  "cli_help_noise": "how stormy the weather is, from 0 to 1",
  "cli_help_file": "load a saved town file instead of a built-in one",
  "cli_list_header": "Built-in towns:",
  "cli_town": "Town: {name}",
  "cli_letter": "Letter from {src} to {dst}: \"{text}\"",
  "cli_route": "Planned route: {path}",
  "cli_no_route": "Right now there is no way from {src} to {dst}.",
  "cli_progress": "step {tick:>5}  {text}",
  "cli_result_delivered": "Delivered after {ticks} steps.",
  "cli_result_failed": "The letter could not get through.",
  "cli_result_timeout": "Still not there after {ticks} steps.",
  "cli_summary": "Envelopes sent: {sent}, sent again: {resent}, lost: {lost}.",
  "cli_unknown_scenario": "Unknown town \"{name}\". Try one of: {names}",
  "cli_unknown_house": "No house called \"{name}\" here. Houses: {names}",
  "cli_bad_cut": "Cannot cut \"{spec}\": write two ends like A-B.",
  "cli_gui_missing": "The window needs Tkinter, which this Python does not have. Try --headless.",
  "cli_story": "What happened:",
}

TR = {
  # general
  "app_title": "Paket Köyü",
  "app_tagline": "Bir mesajın minik bir internette zarf zarf nasıl yol aldığını izle.",
  "router_label": "Postane {tag}",
  "unknown_place": "bir yerde",

  # scenarios
  "sc_village": "Küçük köy",
  "sc_village_blurb": "Altı ev, beş postane ve her yere birden fazla yol.",
  "sc_bridges": "İki tepe",
  "sc_bridges_blurb": "Dar bir köprü ve uzun bir dolambaçla bağlanan iki mahalle.",
  "sc_ring": "Yuvarlak kasaba",
  "sc_ring_blurb": "Çember gibi dizilmiş postaneler. Bir kabloyu kes, posta uzun yoldan gitsin.",
  "sc_grid": "Kalabalık şehir",
  "sc_grid_blurb": "Birbirine eşit pek çok yolu olan ızgara gibi sokaklar.",
  "sc_random": "Rastgele kasaba",
  "sc_loaded": "Dosyadan gelen kasaba",

  # demo letters
  "demo_1": "Köyün öbür ucundan selamlar!",
  "demo_2": "Her zarf eve giden yolu kendi bulur.",
  "demo_3": "Ben yoldayken bir kabloyu kesmeyi dene.",
  "demo_4": "Uzun mektuplar küçük parçalar halinde yolculuk eder.",

  # events
  "ev_sent": "{src}, {dst} için bir mektup yolladı; mektup {pieces} zarfa bölündü.",
  "ev_delivered": "{dst}, {src} tarafından gönderilen mektubun tamamını {ticks} adımda aldı.",
  "ev_failed": "{src} pes etti: {dst} için yazılan mektup yerine ulaşamadı.",
  "ev_resend": "{num}. zarf için henüz teşekkür notu gelmedi, zarf yeniden yollanıyor.",
  "ev_drop_queue": "{num}. zarf {node} noktasında çöpe gitti: raf doluydu.",
  "ev_drop_noise": "{num}. zarf {node} yolunda ıslandı ve okunamaz hale geldi.",
  "ev_drop_no_route": "{num}. zarf {node} noktasında kaldı: oradaki kimse yolu bilmiyordu.",
  "ev_drop_ttl": "{num}. zarf çok uzun süre dolaştı ve {node} noktasında emekliye ayrıldı.",
  "ev_drop_cut": "{num}. zarf {node} yakınında kesik bir kablodan düştü.",
  "ev_cut": "Çat! {a} ile {b} arasındaki kablo kesildi. Onunla birlikte kaybolan zarf: {lost}.",
  "ev_repair": "{a} ile {b} arasındaki kablo yeniden çalışıyor.",
  "ev_settled": "Haberler {rounds} tur boyunca elden ele geçti; artık her postanenin haritası güncel.",

  # errors
  "err_unknown_house": "Lütfen hem göndereni hem de alıcıyı seç.",
  "err_same_house": "Gönderen ile alıcı iki farklı ev olmalı.",
  "err_empty_message": "Önce bir şeyler yaz.",
  "err_no_cable": "Orada kablo yok.",
  "err_file_read": "Dosya okunamadı: {detail}",
  "err_file_write": "Dosya kaydedilemedi: {detail}",
  "err_file_json": "Bu bir kasaba dosyası değil ({line}. satırda bozuk JSON var).",
  "err_file_format": "Bu dosya bir Paket Köyü kasabası değil.",
  "err_file_version": "Bu kasaba daha yeni bir sürümle kaydedilmiş (biçim {version}).",
  "err_file_town": "Dosyadaki kasaba anlamsız görünüyor: {detail}",
  "err_file_empty": "Bu kasabada ikiden az ev var, kimse mektup gönderemez.",

  # window: top bar
  "lbl_town": "Kasaba:",
  "btn_random": "Yeni rastgele kasaba",
  "btn_open": "Aç…",
  "btn_save": "Kaydet…",
  "btn_pause": "Durdur",
  "btn_play": "Oynat",

  # window: sending
  "sec_send": "Mektup gönder",
  "lbl_from": "Kimden",
  "lbl_to": "Kime",
  "btn_send": "Gönder",

  # window: progress
  "sec_progress": "Yolda",
  "progress_idle": "Henüz yolda mektup yok.",
  "progress_moving": "{total} zarftan {got} tanesi ulaştı",
  "progress_done": "{ticks} adımda teslim edildi!",
  "progress_failed": "Yerine ulaşamadı. Bir kabloyu onarıp yeniden dene.",

  # window: knobs
  "sec_controls": "Ayarlar",
  "lbl_speed": "Hız",
  "lbl_chatter": "Sokak kalabalığı",
  "lbl_noise": "Fırtına",
  "lbl_queue": "Raf boyu",
  "lbl_chunk": "Zarf başına harf",
  "chk_way": "Yolu göster",
  "btn_repair": "Bütün kabloları onar",

  # window: counters
  "sec_stats": "Sayaçlar",
  "st_step": "Adım",
  "st_sent": "Gönderilen zarf",
  "st_arrived": "Ulaşan",
  "st_lost": "Kaybolan",
  "st_resent": "Yeniden gönderilen",
  "st_letters": "Teslim edilen mektup",
  "st_trip": "Ortalama yol",
  "st_steps": "{n} adım",
  "st_none": "–",

  # window: inspector
  "sec_inspect": "Yakından bak",
  "inspect_hint": "Neler bildiğini görmek için bir eve ya da postaneye tıkla.",
  "inspect_house": "{name} bir ev.",
  "inspect_router": "{name} bir postane.",
  "inspect_cables": "Çalışan kablolar: {count} kablodan {up} tanesi",
  "inspect_waiting": "raflarında bekleyen zarf: {count}",
  "inspect_knows": "Her eve hangi yoldan gidilir:",
  "inspect_route": "{dest}: {hop} üzerinden (maliyet {cost})",
  "inspect_noroute": "{dest}: henüz bilmiyor",

  # window: story and hints
  "sec_story": "Az önce neler oldu",
  "hint_bar": "Bir kabloyu kesmek için üstüne tıkla, onarmak için yeniden tıkla. Evleri ve postaneleri sürükleyebilirsin.",
  "status_healing": "Postaneler haritalarını yeniden çiziyor…",
  "status_settled": "Her postane yolu biliyor.",
  "legend_data": "mektup parçası",
  "legend_ack": "teşekkür notu",
  "legend_other": "başkalarının postası",
  "legend_cut": "kesik kablo",

  # dialogs
  "dlg_open_title": "Bir kasaba aç",
  "dlg_save_title": "Bu kasabayı kaydet",
  "dlg_error_title": "Bir şeyler ters gitti",
  "file_type": "Kasaba dosyaları",
  "file_all": "Bütün dosyalar",

  # command line
  "cli_description": "Paket Köyü: bir mesajın minik bir internetten geçişini izle. Seçenek verilmezse pencere açılır.",
  "cli_usage": "kullanım: ",
  "cli_options": "seçenekler",
  "cli_help_help": "bu yardımı göster ve çık",
  "cli_help_lang": "bütün metinlerin dili (tr ya da en)",
  "cli_help_headless": "pencere açmak yerine terminalde çalıştır",
  "cli_help_list": "hazır kasabaları listele ve çık",
  "cli_help_scenario": "hangi kasaba kullanılsın",
  "cli_help_from": "gönderen evin adı",
  "cli_help_to": "alıcı evin adı",
  "cli_help_message": "gönderilecek mektup",
  "cli_help_ticks": "bu kadar adımdan sonra vazgeç",
  "cli_help_seed": "tekrarlanabilir çalıştırmalar için rastgelelik tohumu",
  "cli_help_cut": "göndermeden önce bir kabloyu kes, örneğin A-B (tekrarlanabilir)",
  "cli_help_chatter": "sokakların ne kadar kalabalık olduğu, 0 ile 1 arası",
  "cli_help_noise": "havanın ne kadar fırtınalı olduğu, 0 ile 1 arası",
  "cli_help_file": "hazır kasaba yerine kaydedilmiş bir kasaba dosyası yükle",
  "cli_list_header": "Hazır kasabalar:",
  "cli_town": "Kasaba: {name}",
  "cli_letter": "{src} → {dst} mektubu: \"{text}\"",
  "cli_route": "Planlanan yol: {path}",
  "cli_no_route": "Şu anda {src} ile {dst} arasında yol yok.",
  "cli_progress": "adım {tick:>5}  {text}",
  "cli_result_delivered": "{ticks} adımda teslim edildi.",
  "cli_result_failed": "Mektup yerine ulaşamadı.",
  "cli_result_timeout": "{ticks} adım geçti, mektup hâlâ yolda.",
  "cli_summary": "Gönderilen zarf: {sent}, yeniden gönderilen: {resent}, kaybolan: {lost}.",
  "cli_unknown_scenario": "\"{name}\" diye bir kasaba yok. Şunlardan birini dene: {names}",
  "cli_unknown_house": "Burada \"{name}\" adında bir ev yok. Evler: {names}",
  "cli_bad_cut": "\"{spec}\" kesilemedi: iki ucu A-B biçiminde yaz.",
  "cli_gui_missing": "Pencere için Tkinter gerekiyor ama bu Python'da yok. --headless ile dene.",
  "cli_story": "Neler oldu:",
}

TABLES = {"en": EN, "tr": TR}
