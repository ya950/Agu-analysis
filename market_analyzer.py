import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import pytz
from snownlp import SnowNLP
import re
import os
from bs4 import BeautifulSoup
import feedparser
import hashlib

# 设置时区
tz = pytz.timezone('Asia/Shanghai')

class AICacheManager:
    """分析结果缓存管理器"""
    
    def __init__(self, cache_dir='ai_cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_key(self, data):
        """生成缓存键"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get_cached_analysis(self, cache_key, max_age_hours=6):
        """获取缓存的分析结果"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=max_age_hours):
                    print(f"✅ 使用缓存的分析结果 (缓存时间: {cache_time})")
                    return cached_data['analysis']
                else:
                    print(f"⏰ 缓存已过期 (缓存时间: {cache_time})")
            except Exception as e:
                print(f"❌ 读取缓存失败: {e}")
        
        return None
    
    def save_analysis(self, cache_key, analysis):
        """保存分析结果到缓存"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'analysis': analysis
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"💾 分析结果已缓存")
        except Exception as e:
            print(f"❌ 保存缓存失败: {e}")
    
    def clean_old_cache(self, max_days=7):
        """清理旧缓存"""
        cutoff_time = datetime.now() - timedelta(days=max_days)
        cleaned_count = 0
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        cleaned_count += 1
                except Exception as e:
                    print(f"清理缓存文件失败 {filename}: {e}")
        
        if cleaned_count > 0:
            print(f"🧹 已清理 {cleaned_count} 个过期缓存文件")

def get_hot_stocks():
    """获取当日热门股票"""
    try:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f3', 'po': '1', 'pz': '10', 'pn': '1', 'np': '1',
            'fltt': '2', 'invt': '2',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
            'fields': 'f12,f14,f3,f62,f8,f9,f5,f6,f16,f46'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data['data'] and data['data']['diff']:
            stocks = []
            for item in data['data']['diff'][:10]:
                stocks.append({
                    'code': item['f12'],
                    'name': item['f14'],
                    'change_pct': round(item['f3'], 2),
                    'price': item['f62'],
                    'volume': item['f8'],
                    'amount': item['f9'],
                    'pe': item['f16'] if item['f16'] else 0,
                    'market_cap': item['f46'],
                    'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                })
            return stocks
    except Exception as e:
        print(f"获取热门股票失败: {str(e)}")
    return []

def get_hot_topics():
    """获取热门讨论话题"""
    topics = []
    
    # 雪球热门话题
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        url = "https://xueqiu.com/statuses/hot/list.json"
        params = {'since_id': -1, 'max_id': -1, 'count': 20}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if 'list' in data:
            for item in data['list']:
                topic = item.get('title', item.get('text', ''))[:100]
                if topic:
                    topics.append({
                        'source': '雪球',
                        'topic': topic,
                        'user': item.get('user', {}).get('screen_name', ''),
                        'replies': item.get('reply_count', 0),
                        'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                    })
    except Exception as e:
        print(f"获取雪球话题失败: {str(e)}")
    
    return topics

def analyze_sentiment(topics):
    """分析市场情绪"""
    if not topics:
        print("⚠️ 没有话题数据，跳过情感分析")
        return None
    
    sentiment_scores = []
    
    for topic in topics:
        try:
            s = SnowNLP(topic['topic'])
            sentiment = s.sentiments
            
            sentiment_scores.append({
                'topic': topic['topic'],
                'source': topic['source'],
                'sentiment': sentiment,
                'classification': 'positive' if sentiment > 0.6 else 'negative' if sentiment < 0.4 else 'neutral'
            })
        except Exception as e:
            print(f"情感分析失败: {str(e)}")
            sentiment_scores.append({
                'topic': topic['topic'],
                'source': topic['source'],
                'sentiment': 0.5,
                'classification': 'neutral'
            })
    
    if sentiment_scores:
        avg_sentiment = sum(s['sentiment'] for s in sentiment_scores) / len(sentiment_scores)
        
        if avg_sentiment > 0.6:
            market_effect = "赚钱效应明显"
            effect_level = "高"
        elif avg_sentiment > 0.5:
            market_effect = "轻微赚钱效应"
            effect_level = "中"
        elif avg_sentiment > 0.4:
            market_effect = "轻微亏钱效应"
            effect_level = "中"
        else:
            market_effect = "亏钱效应明显"
            effect_level = "高"
        
        return {
            'sentiment_scores': sentiment_scores,
            'avg_sentiment': round(avg_sentiment, 3),
            'market_effect': market_effect,
            'effect_level': effect_level,
            'positive_count': sum(1 for s in sentiment_scores if s['classification'] == 'positive'),
            'negative_count': sum(1 for s in sentiment_scores if s['classification'] == 'negative'),
            'neutral_count': sum(1 for s in sentiment_scores if s['classification'] == 'neutral')
        }
    
    return None

def get_hot_themes():
    """获取各大网站热点题材"""
    themes = []
    
    # 东方财富热门概念板块
    try:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f3', 'po': '1', 'pz': '20', 'pn': '1', 'np': '1',
            'fltt': '2', 'invt': '2',
            'fs': 'm:90+t:2',
            'fields': 'f12,f14,f3,f62,f136'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data['data'] and data['data']['diff']:
            for item in data['data']['diff']:
                themes.append({
                    'source': '东方财富',
                    'theme_name': item['f14'],
                    'theme_code': item['f12'],
                    'change_pct': round(item['f3'], 2),
                    'leading_stock': item.get('f136', ''),
                    'type': '概念板块',
                    'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception as e:
        print(f"获取东方财富热点题材失败: {str(e)}")
    
    # 从雪球话题中提取题材
    try:
        xueqiu_topics = get_hot_topics()
        
        theme_keywords = [
            '人工智能', 'AI', '芯片', '半导体', '新能源', '锂电池', '光伏', 
            '医药', '生物', '消费', '白酒', '军工', '国企改革', '元宇宙',
            '数字经济', '机器人', '自动驾驶', '储能', '氢能', '风电'
        ]
        
        for topic in xueqiu_topics:
            topic_text = topic['topic']
            for keyword in theme_keywords:
                if keyword in topic_text:
                    themes.append({
                        'source': '雪球',
                        'theme_name': keyword,
                        'theme_code': '',
                        'change_pct': 0,
                        'leading_stock': '',
                        'type': '话题题材',
                        'original_topic': topic_text,
                        'replies': topic['replies'],
                        'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                    })
                    break
    except Exception as e:
        print(f"从雪球提取题材失败: {str(e)}")
    
    return themes

def analyze_theme_popularity(themes, news_list):
    """分析题材热度"""
    theme_stats = {}
    
    for theme in themes:
        theme_name = theme['theme_name']
        if theme_name not in theme_stats:
            theme_stats[theme_name] = {
                'count': 0, 'total_change': 0, 'sources': set(),
                'leading_stocks': set(), 'related_news': []
            }
        
        theme_stats[theme_name]['count'] += 1
        theme_stats[theme_name]['total_change'] += theme['change_pct']
        theme_stats[theme_name]['sources'].add(theme['source'])
        
        if theme['leading_stock']:
            leading_stock = str(theme['leading_stock'])
            if leading_stock.strip():
                theme_stats[theme_name]['leading_stocks'].add(leading_stock)
    
    for news in news_list:
        news_text = f"{news['title']} {news['summary']}".lower()
        for theme_name in theme_stats:
            if theme_name.lower() in news_text:
                theme_stats[theme_name]['related_news'].append({
                    'title': news['title'],
                    'source': news['source'],
                    'link': news['link']
                })
    
    theme_ranking = []
    for theme_name, stats in theme_stats.items():
        avg_change = stats['total_change'] / stats['count'] if stats['count'] > 0 else 0
        news_count = len(stats['related_news'])
        source_count = len(stats['sources'])
        
        popularity_score = (
            stats['count'] * 0.4 +
            (avg_change / 10) * 0.3 +
            news_count * 0.2 +
            source_count * 0.1
        )
        
        theme_ranking.append({
            'theme_name': theme_name,
            'popularity_score': round(popularity_score, 2),
            'count': stats['count'],
            'avg_change': round(avg_change, 2),
            'news_count': news_count,
            'source_count': source_count,
            'leading_stocks': list(stats['leading_stocks'])[:3],
            'related_news': stats['related_news'][:3]
        })
    
    theme_ranking.sort(key=lambda x: x['popularity_score'], reverse=True)
    return theme_ranking[:10]

def collect_industry_news():
    """收集行业热点新闻"""
    news_list = []
    
    # 新浪财经行业新闻
    try:
        url = "https://rss.sina.com.cn/finance/stock/hydt.xml"
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:10]:
            news_list.append({
                'title': entry.title,
                'summary': entry.summary if hasattr(entry, 'summary') else '',
                'link': entry.link,
                'published': entry.published if hasattr(entry, 'published') else '',
                'source': '新浪财经'
            })
    except Exception as e:
        print(f"获取新浪行业新闻失败: {str(e)}")
    
    # 东方财富行业新闻
    try:
        url = "http://finance.eastmoney.com/news/cyfj.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.eastmoney.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"东方财富行业新闻页面返回状态码: {response.status_code}")
            return news_list
            
        soup = BeautifulSoup(response.text, 'lxml')
        
        news_items = soup.select('.list-item')[:10]
        if not news_items:
            news_items = soup.select('.news-item')[:10]
        if not news_items:
            news_items = soup.select('li')[:10]
            
        print(f"找到 {len(news_items)} 条新闻")
        
        for item in news_items:
            title_elem = item.select_one('.title')
            link_elem = item.select_one('a')
            time_elem = item.select_one('.time')
            
            if title_elem and link_elem:
                news_list.append({
                    'title': title_elem.get_text(strip=True),
                    'summary': '',
                    'link': link_elem['href'] if link_elem.has_attr('href') else '',
                    'published': time_elem.get_text(strip=True) if time_elem else '',
                    'source': '东方财富'
                })
    except Exception as e:
        print(f"获取东方财富行业新闻失败: {str(e)}")
    
    return news_list

# ===== 智能规则分析函数 =====

def calculate_market_strength(hot_stocks, sentiment):
    """计算市场强度指标"""
    if not hot_stocks:
        return {'level': '弱市', 'score': 3, 'features': '缺乏热点'}
    
    # 添加空值检查
    if sentiment is None:
        sentiment = {'avg_sentiment': 0.5}  # 使用默认值
    
    avg_change = sum(s['change_pct'] for s in hot_stocks[:5]) / len(hot_stocks[:5])
    sentiment_score = sentiment.get('avg_sentiment', 0.5)
    
    # 计算成交量强度（相对值）
    volume_strength = sum(s['amount'] for s in hot_stocks[:5]) / 5
    volume_normalized = min(volume_strength / 1000000, 1)  # 归一化到0-1
    
    # 综合评分计算
    score = (avg_change / 10) * 4 + sentiment_score * 3 + volume_normalized * 3
    
    # 确定市场强度等级
    if score >= 7:
        return {
            'level': '强市',
            'score': round(score, 1),
            'features': '普涨格局，资金活跃，赚钱效应明显'
        }
    elif score >= 5:
        return {
            'level': '震荡市',
            'score': round(score, 1),
            'features': '结构性行情，分化明显，局部热点'
        }
    else:
        return {
            'level': '弱市',
            'score': round(score, 1),
            'features': '调整格局，谨慎为主，防御为上'
        }

def analyze_themes_deep(themes):
    """深度分析热点题材"""
    if not themes:
        return "暂无明显热点题材，市场缺乏主线方向"
    
    analysis = ""
    for i, theme in enumerate(themes[:3], 1):
        # 评估题材持续性
        sustainability = "高" if theme['popularity_score'] > 7 else "中" if theme['popularity_score'] > 4 else "低"
        
        # 评估题材动量
        momentum = "强" if theme['avg_change'] > 3 else "中等" if theme['avg_change'] > 0 else "弱"
        
        # 评估题材热度
        heat_level = "高热" if theme['popularity_score'] > 8 else "活跃" if theme['popularity_score'] > 5 else "一般"
        
        analysis += f"""
**{i}. {theme['theme_name']}**
- 持续性: {sustainability} | 动量: {momentum} | 热度: {heat_level}
- 热度评分: {theme['popularity_score']} | 平均涨幅: {theme['avg_change']}%
- 领涨股: {', '.join(theme['leading_stocks'][:2]) if theme['leading_stocks'] else '暂无龙头'}
- 关注度: {theme['source_count']}个平台提及 | {theme['news_count']}条相关新闻

"""
    
    return analysis

def assess_risks(hot_stocks, sentiment, themes):
    """智能风险评估"""
    risks = []
    opportunities = []
    
    # 添加空值检查
    if sentiment is None:
        sentiment = {'avg_sentiment': 0.5}
    
    # 检查涨幅风险
    if hot_stocks:
        top_gain = hot_stocks[0]['change_pct']
        if top_gain > 8:
            risks.append("短期涨幅过大，获利回吐压力增加")
        elif top_gain > 5:
            risks.append("部分个股涨幅较大，注意分化")
    
    # 检查情绪风险
    sentiment_score = sentiment.get('avg_sentiment', 0.5)
    if sentiment_score > 0.8:
        risks.append("市场情绪过热，需警惕冲高回落")
    elif sentiment_score < 0.3:
        opportunities.append("市场情绪低迷，可能存在超跌机会")
    
    # 检查成交量风险
    if hot_stocks:
        avg_volume = sum(s['amount'] for s in hot_stocks[:5]) / 5
        if avg_volume < 500000:  # 50万
            risks.append("成交量不足，上涨动力有限")
        elif avg_volume > 2000000:  # 200万
            opportunities.append("成交量活跃，市场参与度高")
    
    # 检查题材风险
    if themes:
        top_theme = themes[0]
        if top_theme['popularity_score'] > 9:
            risks.append(f"{top_theme['theme_name']}题材过热，注意追高风险")
        elif top_theme['avg_change'] > 5:
            opportunities.append(f"{top_theme['theme_name']}题材动量强劲，可持续关注")
    
    # 确定风险等级
    risk_level = "高" if len(risks) >= 3 else "中" if len(risks) >= 1 else "低"
    
    # 仓位建议
    if risk_level == "高":
        position_suggestion = "3-5成（轻仓防御）"
    elif risk_level == "中":
        position_suggestion = "5-7成（适中仓位）"
    else:
        position_suggestion = "7-8成（积极布局）"
    
    return {
        'level': risk_level,
        'risks': risks,
        'opportunities': opportunities,
        'position_suggestion': position_suggestion
    }

def generate_strategy(market_strength, risk_assessment, themes):
    """生成操作策略"""
    strategy = ""
    
    # 基于市场强度和风险的策略
    if market_strength['level'] == '强市' and risk_assessment['level'] == '低':
        strategy = """
**📈 积极进攻策略**
- 仓位建议：7-8成，积极参与
- 选股方向：强势题材龙头，放量突破个股
- 操作方法：逢低吸纳，持股待涨，适当追高
- 止损设置：5-8%止损，让利润奔跑
"""
    elif market_strength['level'] == '强市' and risk_assessment['level'] == '中':
        strategy = """
**⚖️ 结构性策略**
- 仓位建议：5-7成，精选个股
- 选股方向：热点题材补涨，低位启动品种
- 操作方法：高抛低吸，波段操作，避免追高
- 止损设置：5%止损，及时止盈
"""
    elif market_strength['level'] == '震荡市':
        strategy = """
**🔄 震荡市策略**
- 仓位建议：3-5成，灵活应对
- 选股方向：超跌反弹，事件驱动
- 操作方法：快进快出，设好止盈止损
- 止损设置：3-5%严格止损
"""
    else:
        strategy = """
**🛡️ 防御策略**
- 仓位建议：2-3成，谨慎观望
- 选股方向：防御性品种，抗跌个股
- 操作方法：多看少动，等待企稳信号
- 止损设置：3%止损，保本第一
"""
    
    # 添加题材建议
    if themes:
        strategy += f"""
**🎯 题材关注**
重点关注：{themes[0]['theme_name']}、{themes[1]['theme_name'] if len(themes) > 1 else ''}
操作建议：回调低吸，不追高，设好止损
"""
    
    return strategy

def generate_default_analysis():
    """生成默认分析（当数据不足时）"""
    return """# 🤖 智能市场分析报告

## 📊 市场强度评估
**强度等级**: 数据不足
**综合评分**: 5.0/10
**主要特征**: 数据获取不完整，建议谨慎操作

## 🔥 热点题材分析
当前无法获取完整的题材数据，建议等待更多数据。

## ⚠️ 风险评估
**风险等级**: 中
**仓位建议**: 3-5成（轻仓观望）

**主要风险**:
- 数据获取不完整，分析准确性受限
- 建议等待更完整的市场数据

## 🎯 操作策略
**观望策略**
- 当前数据不完整，建议暂时观望
- 等待系统恢复正常后再做决策
- 保持轻仓，控制风险

---
*分析时间: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} | 智能规则引擎生成*"""

def enhanced_rule_based_analysis(data):
    """增强版智能规则分析"""
    hot_stocks = data.get('hot_stocks', [])
    sentiment = data.get('sentiment_analysis', {})
    themes = data.get('theme_analysis', [])
    
    print("🧠 开始智能规则分析...")
    
    # 添加数据有效性检查
    if not hot_stocks:
        print("⚠️ 热门股票数据为空，使用默认分析")
        return generate_default_analysis()
    
    # 执行各项分析
    market_strength = calculate_market_strength(hot_stocks, sentiment)
    theme_analysis = analyze_themes_deep(themes)
    risk_assessment = assess_risks(hot_stocks, sentiment, themes)
    strategy = generate_strategy(market_strength, risk_assessment, themes)
    
    # 生成格式化报告
    analysis = f"""# 🤖 智能市场分析报告

## 📊 市场强度评估
**强度等级**: {market_strength['level']}
**综合评分**: {market_strength['score']}/10
**主要特征**: {market_strength['features']}

## 🔥 热点题材深度分析
{theme_analysis}

## ⚠️ 风险评估
**风险等级**: {risk_assessment['level']}
**仓位建议**: {risk_assessment['position_suggestion']}

**主要风险**:
{chr(10).join(f"- {risk}" for risk in risk_assessment['risks']) if risk_assessment['risks'] else "- 当前市场风险相对可控"}

**机会提示**:
{chr(10).join(f"- {opp}" for opp in risk_assessment['opportunities']) if risk_assessment['opportunities'] else "- 耐心等待更好的介入时机"}

## 🎯 操作策略
{strategy}

---
*分析时间: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')} | 智能规则引擎生成*"""
    
    print("✅ 智能规则分析完成")
    return analysis

def get_intelligent_analysis(data, cache_manager):
    """获取智能分析（带缓存）"""
    print("🤖 开始智能分析...")
    
    # 生成缓存键
    cache_key = cache_manager.get_cache_key(data)
    
    # 1. 检查缓存
    cached_analysis = cache_manager.get_cached_analysis(cache_key)
    if cached_analysis:
        return cached_analysis
    
    # 2. 使用智能规则分析
    analysis_result = enhanced_rule_based_analysis(data)
    
    # 3. 保存到缓存
    cache_manager.save_analysis(cache_key, analysis_result)
    
    return analysis_result

def generate_enhanced_report(hot_stocks, sentiment_analysis, theme_analysis, industry_news):
    """生成增强版分析报告（包含智能分析）"""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    
    # 创建报告目录
    os.makedirs('reports', exist_ok=True)
    
    # 初始化缓存管理器
    cache_manager = AICacheManager()
    
    # 定期清理旧缓存
    cache_manager.clean_old_cache()
    
    # 准备分析数据
    analysis_data = {
        'hot_stocks': hot_stocks,
        'sentiment_analysis': sentiment_analysis,
        'theme_analysis': theme_analysis,
        'industry_news': industry_news
    }
    
    # 获取智能分析
    intelligent_analysis = get_intelligent_analysis(analysis_data, cache_manager)
    
    # 生成增强版Markdown报告
    md_content = f"""# A股市场综合分析报告 ({today})

> 🤖 本报告包含智能分析，提供专业的市场洞察和操作建议

---

## 📈 今日热门股票TOP10

| 排名 | 股票代码 | 股票名称 | 涨跌幅(%) | 最新价 | 成交量(手) | 成交额(万) | 市盈率 | 市值(亿) |
|------|----------|----------|-----------|--------|------------|------------|--------|----------|
"""
    
    for i, stock in enumerate(hot_stocks, 1):
        md_content += f"| {i} | {stock['code']} | {stock['name']} | {stock['change_pct']}% | {stock['price']} | {stock['volume']:,} | {stock['amount']/10000:,.2f} | {stock['pe']} | {stock['market_cap']/100000000:,.2f} |\n"
    
    if sentiment_analysis:
        md_content += f"""
## 📊 市场情绪分析

### 整体市场情绪
- **平均情感分数**: {sentiment_analysis['avg_sentiment']} (0-1，越接近1越正面)
- **市场效应**: {sentiment_analysis['market_effect']} ({sentiment_analysis['effect_level']})
- **话题分布**: 
  - 正面: {sentiment_analysis['positive_count']} 条
  - 中性: {sentiment_analysis['neutral_count']} 条
  - 负面: {sentiment_analysis['negative_count']} 条

### 热门话题情感分析
| 话题来源 | 话题内容 | 情感分数 | 分类 |
|----------|----------|----------|------|
"""
        
        for score in sentiment_analysis['sentiment_scores'][:10]:
            topic_preview = score['topic'][:50] + '...' if len(score['topic']) > 50 else score['topic']
            md_content += f"| {score['source']} | {topic_preview} | {score['sentiment']:.3f} | {score['classification']} |\n"
    
    md_content += f"""
## 🔥 热点题材分析TOP10

| 排名 | 题材名称 | 热度分数 | 出现次数 | 平均涨幅(%) | 相关新闻数 | 领涨股 |
|------|----------|----------|----------|-------------|------------|--------|
"""
    
    for i, theme in enumerate(theme_analysis, 1):
        leading_stocks = ', '.join(str(stock) for stock in theme['leading_stocks'][:2]) if theme['leading_stocks'] else '无'
        md_content += f"| {i} | {theme['theme_name']} | {theme['popularity_score']} | {theme['count']} | {theme['avg_change']} | {theme['news_count']} | {leading_stocks} |\n"
    
    # 添加智能分析部分
    md_content += f"""

---

## 🤖 智能分析报告

{intelligent_analysis}

---

## 📋 原始数据详情

### 热点题材详细分析

"""
    
    for theme in theme_analysis[:5]:
        md_content += f"""
#### {theme['theme_name']} (热度: {theme['popularity_score']})
- **出现次数**: {theme['count']} 次
- **平均涨幅**: {theme['avg_change']}%
- **相关新闻**: {theme['news_count']} 条
- **领涨股**: {', '.join(str(stock) for stock in theme['leading_stocks']) if theme['leading_stocks'] else '无'}
- **数据源**: {theme['source_count']} 个平台
- **相关新闻**:
"""
        for news in theme['related_news'][:2]:
            md_content += f"  - [{news['title']}]({news['link']}) - {news['source']}\n"
    
    md_content += f"""
### 最新行业新闻

"""
    
    for news in industry_news[:5]:
        md_content += f"""
- **{news['source']}**: [{news['title']}]({news['link']})
  - 发布时间: {news['published']}
  - 摘要: {news['summary'][:100]}...
"""
    
    md_content += f"""

---

## 📈 分析说明

### 📊 数据来源
- **热门股票**: 东方财富API实时数据
- **市场情绪**: 雪球、东方财富股吧话题分析
- **热点题材**: 概念板块+话题关键词提取
- **行业新闻**: 新浪RSS、东方财富行业新闻

### 🧠 分析方法
- **市场强度**: 综合涨幅、情绪、成交量计算
- **题材评估**: 热度、持续性、动量多维度分析
- **风险评估**: 涨幅、情绪、成交量风险识别
- **策略生成**: 基于市场强度和风险的智能匹配

### ⚠️ 免责声明
本报告由智能规则引擎生成，仅供参考，不构成投资建议。
投资有风险，决策需谨慎，请根据自身风险承受能力做出投资决策。

---
*报告生成时间: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}*
*智能分析引擎: 规则分析 v1.0*
"""
    
    # 保存增强版报告
    with open(f'reports/enhanced_report_{today}.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    # 更新主README
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(f"""# A股市场智能分析系统

## 🤖 智能分析报告 ({today})

> 🚀 基于规则引擎的智能市场分析，提供专业的投资洞察

### 📈 今日热门股票TOP3
""")
        for stock in hot_stocks[:3]:
            f.write(f"- **{stock['name']} ({stock['code']})**: {stock['change_pct']}% | 成交额: {stock['amount']/10000:,.2f}万\n")
        
        if sentiment_analysis:
            f.write(f"""
### 📊 市场情绪
- **当前效应**: {sentiment_analysis['market_effect']} ({sentiment_analysis['effect_level']})
- **情感分数**: {sentiment_analysis['avg_sentiment']}
""")
        
        f.write(f"""
### 🔥 热点题材TOP3
""")
        for theme in theme_analysis[:3]:
            f.write(f"- **{theme['theme_name']}**: 热度 {theme['popularity_score']} | 平均涨幅 {theme['avg_change']}%\n")
        
        f.write(f"""
### 🤖 智能分析亮点
- [查看完整智能分析报告](reports/enhanced_report_{today}.md)
- 包含市场强度评估、风险分析、操作策略

### 📄 完整报告
- [智能分析报告](reports/enhanced_report_{today}.md) ⭐ 推荐
- [历史报告存档](reports/)

### 🔄 更新时间
- 每交易日9:00和15点自动更新（北京时间）
- 最后更新: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}

### 💡 系统特点
- ✅ 完全免费，无需API密钥
- ✅ 智能规则引擎，专业分析
- ✅ 多维度风险评估
- ✅ 个性化操作策略
""")

def generate_comprehensive_report(hot_stocks, sentiment_analysis, theme_analysis):
    """生成标准版分析报告"""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    
    # 创建报告目录
    os.makedirs('reports', exist_ok=True)
    
    # 生成JSON报告
    report = {
        'date': today,
        'hot_stocks': hot_stocks,
        'sentiment_analysis': sentiment_analysis,
        'theme_analysis': theme_analysis,
        'generated_at': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(f'reports/comprehensive_report_{today}.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 生成Markdown报告
    md_content = f"""# A股市场分析报告 ({today})

## 📈 今日热门股票TOP10

| 排名 | 股票代码 | 股票名称 | 涨跌幅(%) | 最新价 | 成交量(手) | 成交额(万) | 市盈率 | 市值(亿) |
|------|----------|----------|-----------|--------|------------|------------|--------|----------|
"""
    
    for i, stock in enumerate(hot_stocks, 1):
        md_content += f"| {i} | {stock['code']} | {stock['name']} | {stock['change_pct']}% | {stock['price']} | {stock['volume']:,} | {stock['amount']/10000:,.2f} | {stock['pe']} | {stock['market_cap']/100000000:,.2f} |\n"
    
    if sentiment_analysis:
        md_content += f"""
## 📊 市场情绪分析

### 整体市场情绪
- **平均情感分数**: {sentiment_analysis['avg_sentiment']} (0-1，越接近1越正面)
- **市场效应**: {sentiment_analysis['market_effect']} ({sentiment_analysis['effect_level']})
- **话题分布**: 
  - 正面: {sentiment_analysis['positive_count']} 条
  - 中性: {sentiment_analysis['neutral_count']} 条
  - 负面: {sentiment_analysis['negative_count']} 条

### 热门话题情感分析
| 话题来源 | 话题内容 | 情感分数 | 分类 |
|----------|----------|----------|------|
"""
        
        for score in sentiment_analysis['sentiment_scores'][:10]:
            topic_preview = score['topic'][:50] + '...' if len(score['topic']) > 50 else score['topic']
            md_content += f"| {score['source']} | {topic_preview} | {score['sentiment']:.3f} | {score['classification']} |\n"
    
    md_content += f"""
## 🔥 热点题材分析TOP10

| 排名 | 题材名称 | 热度分数 | 出现次数 | 平均涨幅(%) | 相关新闻数 | 领涨股 |
|------|----------|----------|----------|-------------|------------|--------|
"""
    
    for i, theme in enumerate(theme_analysis, 1):
        leading_stocks = ', '.join(str(stock) for stock in theme['leading_stocks'][:2]) if theme['leading_stocks'] else '无'
        md_content += f"| {i} | {theme['theme_name']} | {theme['popularity_score']} | {theme['count']} | {theme['avg_change']} | {theme['news_count']} | {leading_stocks} |\n"
    
    md_content += f"""
### 热点题材详情

"""
    
    for theme in theme_analysis[:5]:
        md_content += f"""
#### {theme['theme_name']} (热度: {theme['popularity_score']})
- **出现次数**: {theme['count']} 次
- **平均涨幅**: {theme['avg_change']}%
- **相关新闻**: {theme['news_count']} 条
- **领涨股**: {', '.join(str(stock) for stock in theme['leading_stocks']) if theme['leading_stocks'] else '无'}
- **相关新闻**:
"""
        for news in theme['related_news'][:2]:
            md_content += f"  - [{news['title']}]({news['link']}) - {news['source']}\n"
    
    md_content += f"""
---
*报告生成时间: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    with open(f'reports/comprehensive_report_{today}.md', 'w', encoding='utf-8') as f:
        f.write(md_content)

def main():
    """主函数"""
    print("开始获取市场数据...")
    
    # 1. 获取热门股票
    hot_stocks = get_hot_stocks()
    print(f"获取到 {len(hot_stocks)} 只热门股票")
    
    # 2. 获取热门话题
    hot_topics = get_hot_topics()
    print(f"获取到 {len(hot_topics)} 条热门话题")
    
    # 3. 分析市场情绪
    sentiment_analysis = analyze_sentiment(hot_topics)
    if sentiment_analysis:
        print(f"市场情绪分析完成: {sentiment_analysis['market_effect']}")
    else:
        print("市场情绪分析失败，将使用默认值")
    
    # 4. 获取热点题材
    hot_themes = get_hot_themes()
    print(f"获取到 {len(hot_themes)} 个热点题材")
    
    # 5. 收集行业新闻
    industry_news = collect_industry_news()
    print(f"获取到 {len(industry_news)} 条行业新闻")
    
    # 6. 分析题材热度
    theme_analysis = analyze_theme_popularity(hot_themes, industry_news)
    print(f"分析完成，前3热门题材: {[t['theme_name'] for t in theme_analysis[:3]]}")
    
    # 7. 生成标准报告
    generate_comprehensive_report(hot_stocks, sentiment_analysis, theme_analysis)
    print("标准市场分析报告生成完成")
    
    # 8. 生成智能增强版报告
    generate_enhanced_report(hot_stocks, sentiment_analysis, theme_analysis, industry_news)
    print("智能增强版市场分析报告生成完成")

if __name__ == "__main__":
    main()
