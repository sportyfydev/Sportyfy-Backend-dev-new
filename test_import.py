import traceback
import sys

try:
    import main
except Exception as e:
    with open('tb.txt', 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
