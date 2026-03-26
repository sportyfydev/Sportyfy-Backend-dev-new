
from main import app
from database import get_supabase

def test_debug():
    print('overrides:', [id(k) for k in app.dependency_overrides.keys()])
    print('get_supabase id:', id(get_supabase))
    for r in app.routes:
        if hasattr(r, 'path') and '/api/v1/kpi/summary' in r.path:
            for d in r.dependant.dependencies:
                if d.call.__name__ == 'get_supabase':
                    print('route get_supabase id:', id(d.call))
