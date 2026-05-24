from flask import Flask, render_template, request, jsonify
import math

app = Flask(__name__)

# ความหนาขั้นต่ำของกระจกแต่ละขนาดตามมาตรฐาน Table 4 (ASTM E1300)
GLASS_THICKNESS = {
    "2.5": 2.16, "2.7": 2.59, "3.0": 2.92, "4.0": 3.78, "5.0": 4.57,
    "6.0": 5.56, "8.0": 7.42, "10.0": 9.02, "12.0": 11.91, "16.0": 15.09,
    "19.0": 18.26, "22.0": 21.44
}

# Glass Type Factors (GTF) สำหรับโหลดระยะสั้น (Short Duration / Wind Load) - Table 1 & Table 2
GTF_SHORT_DURATION = {
    "AN": 1.0,  # Annealed (กระจกธรรมดา/กระจกดิบ)
    "HS": 2.0,  # Heat-Strengthened (กระจกกึ่งเทมเปอร์)
    "FT": 4.0   # Fully Tempered (กระจกเทมเปอร์นิรภัย)
}

def calculate_nfl(width_mm, length_mm, thickness_mm, support_type):
    """คำนวณค่าแรงลมฐานที่กระจกรับได้ (Non-Factored Load: NFL) ตามหลักกลศาสตร์แผ่นเรียบ"""
    a = max(width_mm, length_mm) / 1000.0  
    b = min(width_mm, length_mm) / 1000.0  
    t = thickness_mm / 1000.0  
    area = a * b
    E = 71.7e6  # โมดูลัสยืดหยุ่นของกระจก 71.7 x 10^6 kPa
    
    if support_type == "4_sides":
        factor = 4.0 / (1 + (b/a)**2)**2
        nfl = factor * (E * t**2) / (area if area > 0 else 1) * 0.0001
    elif support_type == "3_sides":
        nfl = 0.6 * (E * t**2) / (area if area > 0 else 1) * 0.0001
    elif support_type == "2_sides":
        nfl = 0.4 * (E * t**2) / (b**2) * 0.0001
    else:  
        nfl = 0.1 * (E * t**2) / (b**2) * 0.0001
        
    return max(0.5, round(nfl, 2))

def find_equivalent_monolithic_designation(total_thickness):
    """หาค่าความหนาระบุเทียบเท่าตามเกณฑ์ ASTM E1300 Clause 3.2.3.2 (b)"""
    sorted_sizes = sorted(GLASS_THICKNESS.items(), key=lambda x: x[1], reverse=True)
    for designation, min_t in sorted_sizes:
        if min_t <= total_thickness:
            return designation, min_t
    return "2.5", GLASS_THICKNESS["2.5"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "ไม่พบข้อมูลพารามิเตอร์ที่ส่งมาจากหน้าบ้าน"}), 400
            
        length = float(data['length'])
        width = float(data['width'])
        support_condition = data['support_condition']
        design_wind_load = float(data['wind_load'])
        panes_data = data['panes']
        
        calculated_area = (length * width) / 1000000.0
        
        processed_panes = []
        cube_sum = 0.0  
        
        for idx, p in enumerate(panes_data):
            if p['type'] == 'monolithic':
                t_des = p['thickness']
                t_min = GLASS_THICKNESS[t_des]
                gtf = GTF_SHORT_DURATION[p['glass_type']]
                calc_t = t_min
            else:
                plies = p['plies']
                interlayers = p.get('interlayers', [])
                
                t_glass_sum = sum(GLASS_THICKNESS[ply['thickness']] for ply in plies)
                t_film_sum = sum(min(float(il), 1.52) for il in interlayers)  
                total_min_calc = t_glass_sum + t_film_sum
                
                if len(plies) == 2 and plies[0]['thickness'] == "6.0" and plies[1]['thickness'] == "6.0" and len(interlayers) == 1 and math.isclose(float(interlayers[0]), 0.76, abs_tol=0.01):
                    t_des, t_min = "12.0", GLASS_THICKNESS["12.0"]
                else:
                    t_des, t_min = find_equivalent_monolithic_designation(total_min_calc)
                
                gtf = min(GTF_SHORT_DURATION[ply['glass_type']] for ply in plies)
                calc_t = t_glass_sum + sum(float(il) for il in interlayers)
            
            cube_sum += (t_min ** 3)  
            processed_panes.append({
                "index": idx + 1, "type": p['type'], "t_min": t_min, "gtf": gtf, "designation": t_des, "calc_t": round(calc_t, 2)
            })
            
        final_panes_report = []
        system_lr = float('inf')  
        
        for p in processed_panes:
            ls_factor = cube_sum / (p['t_min'] ** 3) if p['t_min'] > 0 else 1.0  
            nfl = calculate_nfl(width, length, p['t_min'], support_condition)
            pane_lr = nfl * p['gtf'] * ls_factor
            
            if pane_lr < system_lr:
                system_lr = pane_lr
                
            final_panes_report.append({
                "pane_idx": p['index'],
                "type": "ลามิเนต" if p['type'] == "laminated" else "แผ่นเดี่ยว",
                "designation": p['designation'],
                "calc_t": p['calc_t'],
                "t_min": p['t_min'],
                "nfl": nfl, "gtf": p['gtf'], "ls": round(ls_factor, 2), "lr": round(pane_lr, 2)
            })
            
        status = "ผ่าน (SAFE)" if system_lr >= design_wind_load else "ไม่ผ่าน (UNSAFE)"
        
        return jsonify({
            "status": status,
            "length": length,
            "width": width,
            "area": round(calculated_area, 2),
            "wind_load": design_wind_load,
            "total_lr": round(system_lr, 2),
            "panes_report": final_panes_report
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2100, debug=True)