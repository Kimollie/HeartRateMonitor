import ujson as json




# data = [{
#             "elapsed_time": 30,
#             "PPI_arr": [1,2,3,4,5],
#             "hr_arr": [1,2,3,4,5]
#             }]
# with open("data.json", "w") as f:
#     json.dump(data, f) 

new_data = {
            "elapsed_time": 30,
            "PPI_arr": [1,2,3,4,5],
            "hr_arr": [1,2,3,4,5]
            }
with open("data.json", "r") as f: 
    data = json.load(f)  
data.append(new_data)
if len(data) > 1:
    data = data[-1:] 
with open("data.json", "w") as f:
    json.dump(data, f) 
    
print(data)