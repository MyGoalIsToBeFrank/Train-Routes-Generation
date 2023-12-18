# -*- coding: utf-8 -*-
"""
Created on Fri Dec  8 19:49:04 2023

@author: Duan Chuyu
"""

import networkx as nx
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

'''''''''''''''''''''''''''''''''''
Step 1: 读取文件并创建图
读取：
points_processed.xlsx 存储所有点信息。
                        注意；经过预处理，确保绝缘节格式为 西-东，且没有额外空格输入等
edges_processed.xlsx  只包含绝缘节、电分段、信号机之间的连接；
            道岔和角顶点视为边的属性，存储在边的'via'属性中
            存储边的信息。注意：输入时视图为单向图，在程序内再构建双向图数据。
routes_processed.xlsx 进路词条。有多条进路时只留下一行，进路数量由程序自行判断

创建：
G: 双向全图
Gwest : 向西边走的进路搜索图
Geast : 向东边走的进路搜索图

可视化： G的可视化

辅助函数：
stringProcess(string) : 206-208 -> 208-206 按照由西向东处理
'''''''''''''''''''''''''''''''''''

# 读取点
points = pd.read_excel('points_processed.xlsx')
points['point'] = points['point'].apply(lambda i : str(i)) #确保名称读取为字符串
points = points.set_index('point')
# 读取边
edges = pd.read_excel('edges_processed.xlsx')


### 创建图
G = nx.DiGraph()
for index, row in points.iterrows():
    G.add_node( index, 
                char=row['point_char'],
                x = row['point_X'],
                y = row['point_Y'])

for index, row in edges.iterrows():
    # 获取边所经过的所有道岔/角顶
    viaItems = str(row['via']).strip().split(',')
    if(len(viaItems)==1 and viaItems[0] == '0'):
        viaItems = []
    # 根据他们的X坐标升序或降序排列，分别对应西向和东向的道岔顺序
    viaItems_east = sorted(viaItems, key = lambda i : points.loc[i,'point_X'])
    viaItems_west = sorted(viaItems, key = lambda i : points.loc[i,'point_X'], reverse = True)
    
    # 确定边的基本信息
    start = row['from']
    end = row['to']
    length_ = row['length']
    # 创建边：edges.xlsx中的边是无向图，但程序中是有向图，所以每行数据建立两条边
    # 如果无向边输入顺序是向east
    if (points.loc[start,'point_X'] < points.loc[end,'point_X']):
        G.add_edge(start, end, length = length_, via = viaItems_east, drc = 'east')
        G.add_edge(end, start, length = length_, via = viaItems_west, drc = 'west')
    # 如果无向边输入顺序时向west
    else:
        G.add_edge(start, end, length = length_, via = viaItems_west, drc = 'west')
        G.add_edge(end, start, length = length_, via = viaItems_east, drc = 'east')

# 可视化
subG = nx.edge_subgraph(G,G.edges)
nx.draw(subG,with_labels = True, pos = nx.spring_layout(subG))
# nx.draw(subG,with_labels = True, pos = nx.circular_layout(subG)) 这个好玩

# 西向和东向的进路图不一样，这样才能防止列车找到带折返的进路
Gwest = G.copy() #向西的进路图
Geast = G.copy() #向东的进路图
dbunch = []
for (start, end) in Gwest.edges():
    if(Gwest[start][end]['drc'] == 'east'):
        dbunch.append((start, end))
Gwest.remove_edges_from(dbunch)
dbunch = []
for (start, end) in Geast.edges():
    if(Geast[start][end]['drc'] == 'west'):
        dbunch.append((start, end))  
Geast.remove_edges_from(dbunch)


'''''''''''''''''''''''''''''''''''
Step 2: 寻路
核心函数：
getPaths(start, end): 返回包含start到end的所有路径(用点list表示)的list
getSeries(start, end): 返回一条边的转折点序列list(包含起点和终点)。比如两个绝缘节之间经过了哪些存在转折的道岔
                        为满足xlsx的格式，在部分list结尾重复最后一个点
辅助函数：
isMonotonic (list): 判断list是否单调不递减或者单调不递增。
isParallel (p, q, s, t): 判断(p,q)与(s,t)是否平行，四个点可以存在重复
points2coords(list): 把点的列表转化为坐标列表。[p1, p2] -> [p1_x, p1_y, p2_x, p2_y]
pointsRemained(list): [p1, p2] -> [p1, 0, p2, 0] 用于输出便于检查的 check.xlsx 文件
'''''''''''''''''''''''''''''''''''

# 判断数列单调性的函数
def isMonotonic(li):
    n = len(li)
    asc, dec = True, True
    if(n <= 1):
        return True
    for i in range(1, n):
        diff = li[i] - li[i-1]
        if(diff > 0):
            dec = False
        if(diff < 0):
            asc = False
    return (asc or dec)

#多条进路时排序函数
def sortPaths(paths):
    #提取两条正线的Y坐标，将该进路目标正线的坐标放在第一位
    mainline_y_list = [points.loc['X','point_Y'],points.loc['XN','point_Y']]
    if paths[0][-1] == 'XN' or paths[0][-1] == 'S':
        mainline_y_list.reverse()
    #根据进路中点的位置判断进路在正线上停留时间的长短，其中在目标正线上的停留时间有更高的权重
    sort_path_list = [0 for i in range(len(paths))]
    for path in range(len(paths)):
        for point in paths[path]:
            if points.loc[point,'point_Y'] == mainline_y_list[0]:
                sort_path_list[path] += 2
            if points.loc[point,'point_Y'] == mainline_y_list[1]:
                sort_path_list[path] += 0.1
    #根据停留时间的长短对进路重新排序
    combined_list = list(zip(paths, sort_path_list))    
    sorted_combined_list = sorted(combined_list, key=lambda x: x[1], reverse=True)    
    sorted_paths = [item[0] for item in sorted_combined_list]
    return sorted_paths

### 输出起点到终点的路径集合
def getPaths(start, end):
    paths = []
    if(points.loc[start,'point_X'] > points.loc[end,'point_X']):
        results = nx.all_simple_paths(Gwest, start, end)
    if(points.loc[start,'point_X'] < points.loc[end,'point_X']):
        results = nx.all_simple_paths(Geast, start, end)
    
    # 动车B线实在属于特例，蓝翊文debug
    if(start == 'XDB' or end == 'XDB'):
        for path in results:
            Y = [points.loc[i,'point_Y'] for i in path]
            paths.append(path)
    
    # 剔除Y不单调的进路
    for path in results:
        Y = [points.loc[i,'point_Y'] for i in path]
        if(isMonotonic(Y)):
            paths.append(path)
    return paths

# 判断两个线段是否平行
def isParallel(a,b,p,q): #(a,b) (p,q)两线段
    xa, ya = points.loc[a,'point_X'], points.loc[a,'point_Y']
    xb, yb = points.loc[b,'point_X'], points.loc[b,'point_Y']
    xp, yp = points.loc[p,'point_X'], points.loc[p,'point_Y']
    xq, yq = points.loc[q,'point_X'], points.loc[q,'point_Y']
    return (ya - yb)*(xp - xq) == (yp - yq)*(xa - xb)

# 根据边来获取转折点序列,也就是point_x, point_y,X1,Y1,X2,Y2对应的点列....
def getSeries(start, end):
    keyPoints = []
    
    # 首先处理只含一个点的情况，比如['X7'],该情况下一定重复
    if(start == end):
        return [start, end]
    
    # 首先把始末点、道岔和角顶一股脑放进去
    keyPoints.append(start)
    via_items = G[start][end]['via'].copy()
    keyPoints.extend(via_items)
    keyPoints.append(end)
    
    # 再来剔除非转折的道岔
    keyPointsCopy = keyPoints.copy() # 请注意这里使用值传递，而不是引用，否则下面的逻辑会出错
    for index, point in enumerate(keyPointsCopy):
        if(points.loc[point,'point_char'] == '道岔'):
            before = keyPointsCopy[index - 1]
            after = keyPointsCopy[index + 1]
            # 如果两边平行，那么就删除道岔
            if( isParallel(before, point, point, after) ):
                keyPoints.remove(point)
   
    # 再判断结尾是否重复,这取决于头尾两段是否平行
    s1, s2, e1, e2 = keyPoints[0], keyPoints[1], keyPoints[-2], keyPoints[-1]
    if(not isParallel(s1, s2, e1, e2)):
        keyPoints.append(e2)
    return keyPoints

def points2coords(li):
    ans = []
    if(li == None):
        return ans
    if(len(li) == 0):
        return ans
    for point in li:
        ans.append(points.loc[point,'point_X'])
        ans.append(points.loc[point,'point_Y'])
        
    # 最后填 0 ,补足14位
    z = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    ans.extend(z[0:14-len(ans)])
    return ans

def pointsRemained(li):
    ans = []
    if(li == None):
        return ans
    if(len(li) == 0):
        return ans
    for point in li:
        ans.append(point)
        ans.append(0)
        
    # 最后填 0 ,补足14位
    z = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    ans.extend(z[0:14-len(ans)])
    
    return ans

def getSwitches(start, end): # 最终输出长度固定为6，空白用X填
    # 首先处理只含一个点的情况，比如['X7'],该情况下一定重复
    if(start == end):
        return ['X','X','X','X','X','X']
    
    # 首先把始末点、道岔和角顶一股脑放进去
    viaItems = G[start][end]['via'].copy() # 防止图被污染
    switches = viaItems
       
    # 再来剔除角顶点
    for index, point in enumerate(switches.copy()): # 防止迭代器本身变化
        if(points.loc[point,'point_char'] == '角顶点'):
            switches.remove(point)
    z = ['X','X','X','X','X','X']
    switches.extend(z[0:6-len(switches)])
    
    return switches
        
# 读取基本格式 format.xlsx
data = pd.read_excel('format.xlsx')
# 读取道岔
routes = pd.read_excel('routes_processed.xlsx')

'''''''''''''''''''''''''''''''''''
Step 3: 写入数据并输出
向文件中写入结果
读取： 
format.xlsx 读入表格基本格式
输出：
final.xlsx 最终结果
check.xlsx 用于检查的文件，其中转折点不是坐标而是点的列表，便于人工检查
'''''''''''''''''''''''''''''''''''

### 接下来开始向data中写入数据！
row_id = 2
# 对于每一对进路始末点
for index1, row in routes.iterrows():
    # 获取这对始末点
    start = row['start_point']  
    end = row['end_point']
    # 获取这对点的所有进路
    paths = getPaths(start, end) 
    # 对于每一条进路
    for index2, path in enumerate(paths):
        
        path.append(path[-1]) # 这是因为最后一行形如[X7,X7]
        # 对于进路的每一条边
        
        for oid in range(1, len(path)): 
            # 获得起点
            point = path[oid - 1]
            # 获取边的所有转折点及其坐标
            series = getSeries(path[oid-1],path[oid])
            coords = points2coords(series)
            
            # 填入每行基本数据
            data.loc[row_id,:] = data.loc[0,:] 
            data['oid'][row_id] = oid
            data['station_yard'][row_id] = row['station_yard']
            data['route_type'][row_id] = row['route_type'] 
            data['start_line'][row_id] = row['start_line']
            data['end_line'][row_id] = row['end_line']
            data['station_yard'][row_id] = row['station_yard']
            data['start_point'][row_id] = row['start_point']
            data['end_point'][row_id] = row['end_point']
            data['route'][row_id] = row['route']
            if(len(paths) > 1):
                data['route'][row_id] += str(index2 + 1)
            
            # 填入关键点！
            data['point'][row_id] = point
            data['point_char'][row_id] = points.loc[point,'point_char']
            
            # 填入转折点坐标！
            series = getSeries(path[oid - 1], path[oid])
            coords = points2coords(series)
            data.loc[row_id, 'point_X':'YZ'] = coords
            if(oid == 1):# XZ,YZ只在oid=1的时候填写
                data['XZ'][row_id] = row['XZ']
                data['YZ'][row_id] = row['YZ']
            
            # 填入道岔！
            switches = getSwitches(path[oid - 1], path[oid])
            data.loc[row_id, 'swith1':'swich6'] = switches
            
            # 很重要
            row_id += 1
            
data.drop(0,axis = 0, inplace = True)
data.to_excel('final.xlsx')


row_id = 2
data = pd.read_excel('format.xlsx')
### 生成用于检查的文件
for index1, row in routes.iterrows():
    # 获取这对始末点
    start = row['start_point']  
    end = row['end_point']
    
    # 获取这对点的所有进路,并对其排序
    paths = getPaths(start, end) 
    sortPaths(paths)
    
    # 对于每一条进路
    for index2, path in enumerate(paths):
        path.append(path[-1]) # 这是因为最后一行形如[X7,X7]
        # 对于进路的每一条边
        
        for oid in range(1, len(path)): 
            # 获得起点
            point = path[oid - 1]
            # 获取边的所有转折点及其坐标
            series = getSeries(path[oid-1],path[oid])
            coords = points2coords(series)
            
            # 填入每行基本数据
            data.loc[row_id,:] = data.loc[0,:] 
            data['oid'][row_id] = oid
            data['station_yard'][row_id] = row['station_yard']
            data['route_type'][row_id] = row['route_type']
            data['start_line'][row_id] = row['start_line']
            data['end_line'][row_id] = row['end_line']
            data['station_yard'][row_id] = row['station_yard']
            data['start_point'][row_id] = row['start_point']
            data['end_point'][row_id] = row['end_point']
            data['route'][row_id] = row['route']
            if(len(paths) > 1):
                data['route'][row_id] += str(index2 + 1)
            
            # 填入关键点！
            data['point'][row_id] = point
            data['point_char'][row_id] = points.loc[point,'point_char']
            
            # 填入转折点坐标！
            series = getSeries(path[oid - 1], path[oid])
            coords = pointsRemained(series)
            data.loc[row_id, 'point_X':'YZ'] = coords
            if(oid == 1):# XZ,YZ只在oid=1的时候填写
                data['XZ'][row_id] = row['XZ']
                data['YZ'][row_id] = row['YZ']
            
            # 填入道岔！
            switches = getSwitches(path[oid - 1], path[oid])
            data.loc[row_id, 'swith1':'swich6'] = switches
            
            # 很重要
            row_id += 1
            
data.drop(0,axis = 0, inplace = True)
data.to_excel('check.xlsx')

### 在最后保留IO,用于测试功能
while True:
    start = input('请输入起点：')
    end = input('请输入终点：')
    paths = getPaths(start, end)
    # 进路排序
    paths = sortPaths(paths)
    for index, path in enumerate(paths):
        print('进路{}:\n\n{}'.format(index + 1,path))
        path.append(path[-1]) # 这是因为最后一行形如[X7,X7]
        for i in range(1, len(path)):
            series = getSeries(path[i-1],path[i])
            coords = points2coords(series)
            print('转折点：')
            print(series)
            print('转折点坐标：')
            print(coords)
            print('\n')
        for i in range(1, len(path)):
            print('道岔：')
            switches = getSwitches(path[i-1],path[i])
            print(switches)








