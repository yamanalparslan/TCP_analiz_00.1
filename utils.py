"""
Ortak yardımcı fonksiyonlar
"""

def parse_id_list(id_string):
    """
    ID listesini parse eder. Virgül ve tire desteği.
    
    Örnekler:
        "1,2,3" -> [1, 2, 3]
        "1-5" -> [1, 2, 3, 4, 5]
        "1,3-5,7" -> [1, 3, 4, 5, 7]
    
    Args:
        id_string (str): Parse edilecek ID string'i
        
    Returns:
        tuple: (parsed_ids: list, errors: list)
            - parsed_ids: Başarıyla parse edilen ID'ler
            - errors: Parse edilemeyen kısımlar
    """
    ids = set()
    errors = []
    
    if not id_string or not id_string.strip():
        return [], ["Boş ID listesi"]
    
    parts = id_string.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Tire ile aralık kontrolü
        if '-' in part:
            try:
                range_parts = part.split('-')
                if len(range_parts) != 2:
                    errors.append(f"Geçersiz aralık formatı: '{part}'")
                    continue
                    
                start, end = map(int, range_parts)
                
                if start > end:
                    errors.append(f"Geçersiz aralık (başlangıç > bitiş): '{part}'")
                    continue
                    
                if start < 1 or end > 255:
                    errors.append(f"ID aralık dışı (1-255): '{part}'")
                    continue
                
                for i in range(start, end + 1):
                    ids.add(i)
                    
            except ValueError:
                errors.append(f"Geçersiz sayı formatı: '{part}'")
        else:
            # Tek ID
            try:
                id_val = int(part)
                if id_val < 1 or id_val > 255:
                    errors.append(f"ID aralık dışı (1-255): '{part}'")
                    continue
                ids.add(id_val)
            except ValueError:
                errors.append(f"Geçersiz sayı: '{part}'")
    
    return sorted(list(ids)), errors


def format_id_list_display(ids):
    """
    ID listesini kullanıcı dostu formatta gösterir.
    
    Args:
        ids (list): ID listesi
        
    Returns:
        str: Formatlanmış string
    """
    if not ids:
        return "Hiç ID yok"
    
    if len(ids) <= 5:
        return f"[{', '.join(map(str, ids))}]"
    
    # Çok fazla ID varsa kısalt
    first_few = ', '.join(map(str, ids[:3]))
    return f"[{first_few}, ... toplam {len(ids)} ID]"
