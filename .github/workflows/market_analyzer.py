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

# 设置时区
tz = pytz.timezone('Asia/Shanghai')

def get_hot_stocks():
    """获取当日热门股票"""
    try:
        # 使用东方财富API获取涨幅榜
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f3',  # 涨幅
            'po': '1',    # 排序
            'pz': '10',   # 每页数量
            'pn': '1',    # 页码
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',  # A股
            'fields': 'f12,f14,f3,f62,f8,f9,f5,f6,f16,f46'  # 代码,名称,涨幅,最新价,成交量,成交额,昨收,今开,市盈率,市值
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
    
    # 1. 雪球热门话题
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = "https://xueqiu.com/statuses/hot/list.json"
        params = {
            'since_id': -1,
            'max_id': -1,
            'count': 20
        }
        
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
    
    # 2. 东方财富股吧热门
    try:
        url = "http://guba.eastmoney.com/rank/api/Article/GetHotArticleList"
        params = {
            'pageSize': 10,
            'pageIndex': 1,
            'sortType': 1  # 按热度排序
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'data' in data and 'list' in data['data']:
            for item in data['data']['list']:
                topics.append({
                    'source': '东方财富股吧',
                    'topic': item.get('title', '')[:100],
                    'user': item.get('nickname', ''),
                    'replies': item.get('read_count', 0),
                    'timestamp': datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception as e:
        print(f"获取东方财富话题失败: {str(e)}")
    
    return topics

def analyze_sentiment(topics):
    """分析市场情绪"""
    sentiment_scores = []
    
    for topic in topics:
        try:
            # 使用SnowNLP进行情感分析
            s = SnowNLP(topic['topic'])
            sentiment = s.sentiments  # 0-1之间，越接近1越正面
            
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
    
    # 计算整体市场情绪
    if sentiment_scores:
        avg_sentiment = sum(s['sentiment'] for s in sentiment_scores) / len(sentiment_scores)
        
        # 判断市场效应
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
    
    # 1. 东方财富热门概念板块
    try:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'fid': 'f3',  # 涨幅
            'po': '1',    # 排序
            'pz': '20',   # 每页数量
            'pn': '1',    # 页码
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fs': 'm:90+t:2',  # 概念板块
            'fields': 'f12,f14,f3,f62,f136'  # 代码,名称,涨幅,最新价,领涨股
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
    
    # 2. 从雪球话题中提取题材
    try:
        xueqiu_topics = get_hot_topics()
        
        # 从话题中提取题材关键词
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
    
    # 统计各题材出现次数和平均涨幅
    for theme in themes:
        theme_name = theme['theme_name']
        if theme_name not in theme_stats:
            theme_stats[theme_name] = {
                'count': 0,
                'total_change': 0,
                'sources': set(),
                'leading_stocks': set(),
                'related_news': []
            }
        
        theme_stats[theme_name]['count'] += 1
        theme_stats[theme_name]['total_change'] += theme['change_pct']
        theme_stats[theme_name]['sources'].add(theme['source'])
        
        if theme['leading_stock']:
            theme_stats[theme_name]['leading_stocks'].add(theme['leading_stock'])
    
    # 关联新闻
    for news in news_list:
        news_text = f"{news['title']} {news['summary']}".lower()
        for theme_name in theme_stats:
            if theme_name.lower() in news_text:
                theme_stats[theme_name]['related_news'].append({
                    'title': news['title'],
                    'source': news['source'],
                    'link': news['link']
                })
    
    # 计算热度分数
    theme_ranking = []
    for theme_name, stats in theme_stats.items():
        # 热度分数 = 出现次数 * 0.4 + 平均涨幅 * 0.3 + 相关新闻数 * 0.2 + 来源数 * 0.1
        avg_change = stats['total_change'] / stats['count'] if stats['count'] > 0 else 0
        news_count = len(stats['related_news'])
        source_count = len(stats['sources'])
        
        popularity_score = (
            stats['count'] * 0.4 +
            (avg_change / 10) * 0.3 +  # 涨幅归一化
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
    
    # 按热度分数排序
    theme_ranking.sort(key=lambda x: x['popularity_score'], reverse=True)
    
    return theme_ranking[:10]

def collect_industry_news():
    """收集行业热点新闻"""
    news_list = []
    
    # 1. 新浪财经行业新闻
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
    
    # 2. 东方财富行业新闻
    try:
        url = "http://finance.eastmoney.com/news/cyfj.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        
        news_items = soup.select('.list-item')[:10]
        
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

def generate_comprehensive_report(hot_stocks, sentiment_analysis, theme_analysis):
    """生成综合市场分析报告"""
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
    md_content = f"""# A股市场综合分析报告 ({today})

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
        leading_stocks = ', '.join(theme['leading_stocks'][:2]) if theme['leading_stocks'] else '-'
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
- **领涨股**: {', '.join(theme['leading_stocks']) if theme['leading_stocks'] else '无'}
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
    
    # 更新主README
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(f"""# A股市场综合分析系统

## 📊 最新市场报告 ({today})

### 今日热门股票TOP3
""")
        for stock in hot_stocks[:3]:
            f.write(f"- **{stock['name']} ({stock['code']})**: {stock['change_pct']}% | 成交额: {stock['amount']/10000:,.2f}万\n")
        
        if sentiment_analysis:
            f.write(f"""
### 市场情绪
- **当前效应**: {sentiment_analysis['market_effect']} ({sentiment_analysis['effect_level']})
- **情感分数**: {sentiment_analysis['avg_sentiment']}
""")
        
        f.write(f"""
### 🔥 热点题材TOP3
""")
        for theme in theme_analysis[:3]:
            f.write(f"- **{theme['theme_name']}**: 热度 {theme['popularity_score']} | 平均涨幅 {theme['avg_change']}%\n")
        
        f.write(f"""
### 📄 完整报告
- [查看今日完整报告](reports/comprehensive_report_{today}.md)
- [历史报告存档](reports/)

### 🔄 更新时间
- 每交易日9:00和15点自动更新（北京时间）
- 最后更新: {datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')}
""")

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
    
    # 4. 获取热点题材
    hot_themes = get_hot_themes()
    print(f"获取到 {len(hot_themes)} 个热点题材")
    
    # 5. 收集行业新闻
    industry_news = collect_industry_news()
    print(f"获取到 {len(industry_news)} 条行业新闻")
    
    # 6. 分析题材热度
    theme_analysis = analyze_theme_popularity(hot_themes, industry_news)
    print(f"分析完成，前3热门题材: {[t['theme_name'] for t in theme_analysis[:3]]}")
    
    # 7. 生成综合报告
    generate_comprehensive_report(hot_stocks, sentiment_analysis, theme_analysis)
    print("综合市场分析报告生成完成")

if __name__ == "__main__":
    main()
