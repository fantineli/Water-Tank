from flask import Flask, render_template_string, send_file, Response, request
from ftplib import FTP
import io
import traceback
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import dates as mdates
from datetime import datetime, timedelta

matplotlib.use('Agg')

# --- CONFIGURAÇÃO FTP ---
SERVIDOR_FTP = "10.100.100.157"
UTILIZADOR = "NeoOne"
SENHA = "Neo@123"
CAMINHO_DA_PASTA_FTP = "WT_HH"
NOME_DO_ARQUIVO_IMAGEM = "HH_LoRa_WTSCR.png"
NOME_DO_ARQUIVO_TXT = "HH_LoRa_WT.txt"

# --- FUNÇÃO DE CONVERSÃO PARA PERCENTUAL ---
def converter_para_percentual(series_dados):
    min_mah = 4.0
    max_mah = 20.0
    percentual = (series_dados - min_mah) * 100 / (max_mah - min_mah)
    return percentual.clip(0, 100)

# --- CONTEÚDO HTML DA PÁGINA PRINCIPAL ---
HTML_PRINCIPAL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WT HOPI HARI</title>
    <style>
        body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f0f0f0; font-family: sans-serif; overflow: hidden; }
        .container { text-align: center; padding: 20px; border: 1px solid #ccc; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 95vw; max-height: 95vh; }
        img { max-width: 100%; max-height: calc(95vh - 120px); height: auto; border: 1px solid #ddd; display: block; }
        .info-bar { width: 100%; display: flex; justify-content: space-between; align-items: baseline; margin-top: 15px; }
        .info-left-group { display: flex; align-items: baseline; }
        .info-title { font-size: 1.1em; font-weight: bold; margin-right: 8px; }
        .info-timestamp { font-size: 0.9em; color: #555; }
        .button { background-color: #007bff; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <img id="imagemDinamica" src="/imagem" alt="Imagem carregada do storage da empresa">
        <div class="info-bar">
            <div class="info-left-group">
                <span class="info-title">WT HOPI HARI</span>
                <span id="timestamp-display" class="info-timestamp"></span>
            </div>
            <a href="/pagina-grafico" class="button">Ver Gráfico</a>
        </div>
    </div>
    <script>
        function atualizarConteudo() {
            var timestampElement = document.getElementById('timestamp-display');
            var dataHoraAtual = new Date().toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
            timestampElement.innerHTML = dataHoraAtual;
            var imgElement = document.getElementById('imagemDinamica');
            var timestamp = new Date().getTime();
            imgElement.src = '/imagem?cachebuster=' + timestamp;
        }
        atualizarConteudo();
        setInterval(atualizarConteudo, 5000);
    </script>
</body>
</html>
"""

# --- CONTEÚDO HTML DA PÁGINA DOS GRÁFICOS (COM SPINNER DE LOADING) ---
HTML_GRAFICO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gráficos de Medições - WT HOPI HARI</title>
    <style>
        * { box-sizing: border-box; }
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            padding: 20px;
            margin: 0;
            background-color: #f0f0f0;
            font-family: sans-serif;
            overflow: hidden;
        }
        .header-container {
            width: 100%;
            max-width: 1800px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-shrink: 0;
        }
        .button-voltar { background-color: #6c757d; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px; font-size: 0.9em; }
        .filter-container { text-align: right; }
        .filter-button { background-color: #fff; color: #333; padding: 8px 12px; font-size: 0.9em; border: 1px solid #ccc; border-radius: 5px; cursor: pointer; margin-left: 8px; }
        .filter-button.active { background-color: #007bff; color: white; border-color: #007bff; }
        
        .main-content {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
            width: 100%;
            max-width: 1800px;
            min-height: 0;
        }
        .grafico-container {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            text-align: center;
            background-color: #fff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            min-height: 0;
        }
        .grafico-container h1 { margin-top: 0; margin-bottom: 10px; font-size: 1.1em; }
        .grafico-wrapper {
            position: relative;
            flex-grow: 1;
            width: 100%;
            height: 100%;
        }
        img {
            width: 100%;
            height: 100%;
            object-fit: fill;
            visibility: hidden;
            opacity: 0;
            transition: visibility 0s, opacity 0.5s linear;
        }
        img.loaded {
            visibility: visible;
            opacity: 1;
        }
        .loader {
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            position: absolute;
            top: 50%;
            left: 50%;
            margin-top: -25px;
            margin-left: -25px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="header-container">
        <a href="/" class="button-voltar">&larr; Voltar</a>
        <div class="filter-container">
            <button class="filter-button active" onclick="definirPeriodo('diario')">Diário</button>
            <button class="filter-button" onclick="definirPeriodo('semanal')">Semanal</button>
            <button class="filter-button" onclick="definirPeriodo('mensal')">Mensal</button>
        </div>
    </div>
    <div class="main-content">
        <div class="grafico-container">
            <h1 id="titulo-t1">Reservatório de Consumo 1</h1>
            <div class="grafico-wrapper">
                <div id="loader1" class="loader"></div>
                <img id="graficoTanque1" src="" alt="Gráfico do Reservatório de Consumo 1">
            </div>
        </div>
        <div class="grafico-container">
            <h1 id="titulo-t2">Reservatório de Consumo 2</h1>
            <div class="grafico-wrapper">
                <div id="loader2" class="loader"></div>
                <img id="graficoTanque2" src="" alt="Gráfico do Reservatório de Consumo 2">
            </div>
        </div>
    </div>
    <script>
        let periodoAtual = 'diario';
        
        function definirPeriodo(periodo) {
            periodoAtual = periodo;
            document.querySelectorAll('.filter-button').forEach(btn => btn.classList.remove('active'));
            document.querySelector(`button[onclick="definirPeriodo('${periodo}')"]`).classList.add('active');
            atualizarGraficos();
        }

        function carregarGrafico(imgId, loaderId, url) {
            const imgElement = document.getElementById(imgId);
            const loaderElement = document.getElementById(loaderId);

            loaderElement.style.display = 'block';
            imgElement.classList.remove('loaded');
            
            imgElement.onload = () => {
                loaderElement.style.display = 'none';
                imgElement.classList.add('loaded');
            };

            imgElement.src = url;
        }

        function atualizarGraficos() {
            const timestamp = new Date().getTime();
            
            const wrapper1 = document.getElementById('graficoTanque1').parentElement;
            const width1 = wrapper1.offsetWidth;
            const height1 = wrapper1.offsetHeight;
            const url1 = `/plot/1?periodo=${periodoAtual}&w=${width1}&h=${height1}&cachebuster=${timestamp}`;
            carregarGrafico('graficoTanque1', 'loader1', url1);

            const wrapper2 = document.getElementById('graficoTanque2').parentElement;
            const width2 = wrapper2.offsetWidth;
            const height2 = wrapper2.offsetHeight;
            const url2 = `/plot/2?periodo=${periodoAtual}&w=${width2}&h=${height2}&cachebuster=${timestamp}`;
            carregarGrafico('graficoTanque2', 'loader2', url2);
            
            const hoje = new Date();
            const dia = String(hoje.getDate()).padStart(2, '0');
            const mes = String(hoje.getMonth() + 1).padStart(2, '0'); // Janeiro é 0!
            const ano = hoje.getFullYear();
            const dataFormatada = `${dia}/${mes}/${ano}`;

            const titulos = { 
                'diario': `Dia: ${dataFormatada}`, 
                'semanal': 'Últimos 7 Dias', 
                'mensal': 'Últimos 30 Dias' 
            };

            document.getElementById('titulo-t1').innerText = `Reservatório de Consumo 1 (${titulos[periodoAtual]})`;
            document.getElementById('titulo-t2').innerText = `Reservatório de Consumo 2 (${titulos[periodoAtual]})`;
        }
        
        document.addEventListener('DOMContentLoaded', atualizarGraficos);
        setInterval(atualizarGraficos, 300000);
        window.addEventListener('resize', atualizarGraficos);
    </script>
</body>
</html>
"""

# --- APLICAÇÃO WEB ---
app = Flask(__name__)

# --- FUNÇÃO AUXILIAR PARA LER OS DADOS ---
def obter_dados_do_ftp():
    ftp = None
    try:
        ftp = FTP(SERVIDOR_FTP)
        ftp.login(user=UTILIZADOR, passwd=SENHA)
        ftp.cwd(CAMINHO_DA_PASTA_FTP)
        dados_txt_em_memoria = io.BytesIO()
        ftp.retrbinary(f"RETR {NOME_DO_ARQUIVO_TXT}", dados_txt_em_memoria.write)
        dados_txt_em_memoria.seek(0)
        
        # --- CORREÇÃO PARA ARQUIVO SEM CABEÇALHO ---
        # Lê o CSV informando que não há cabeçalho (header=None). A primeira coluna (0)
        # é usada como índice e formatada como data.
        df = pd.read_csv(dados_txt_em_memoria, header=None, index_col=0, parse_dates=True)
        
        # Renomeia as colunas restantes (que o pandas nomeia como 1 e 2)
        # para os nomes que o restante do código espera.
        df.rename(columns={1: 'SENSOR 1', 2: 'SENSOR 2'}, inplace=True)
        
        print(f"Colunas do DataFrame após o tratamento: {df.columns.tolist()}")
        
        return df
    finally:
        if ftp:
            ftp.quit()

@app.route("/")
def pagina_principal():
    return render_template_string(HTML_PRINCIPAL)

@app.route("/imagem")
def servir_imagem():
    ftp = None
    try:
        ftp = FTP(SERVIDOR_FTP)
        ftp.login(user=UTILIZADOR, passwd=SENHA)
        ftp.cwd(CAMINHO_DA_PASTA_FTP)
        arquivo_em_memoria = io.BytesIO()
        ftp.retrbinary(f"RETR {NOME_DO_ARQUIVO_IMAGEM}", arquivo_em_memoria.write)
        arquivo_em_memoria.seek(0)
        return send_file(arquivo_em_memoria, mimetype='image/png')
    except Exception as e:
        print(f"ERRO AO BUSCAR IMAGEM PRINCIPAL: {e}")
        return Response(f"Erro ao buscar imagem: {e}", status=500)
    finally:
        if ftp:
            ftp.quit()

@app.route("/pagina-grafico")
def pagina_grafico():
    return render_template_string(HTML_GRAFICO)

@app.route("/plot/<int:tanque_id>")
def servir_grafico(tanque_id):
    try:
        width = request.args.get('w', default=1200, type=int)
        height = request.args.get('h', default=400, type=int)
        dpi = 100

        periodo = request.args.get('periodo', 'diario')
        df_completo = obter_dados_do_ftp()

        if not df_completo.empty:
            timespan_total = df_completo.index.max() - df_completo.index.min()
        else:
            timespan_total = timedelta(days=0)

        mostrar_aviso = False
        if periodo == 'semanal' and timespan_total < timedelta(days=6):
            mostrar_aviso = True
        elif periodo == 'mensal' and timespan_total < timedelta(days=29):
            mostrar_aviso = True
        
        if mostrar_aviso or df_completo.empty or width < 10 or height < 10:
            fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax.text(0.5, 0.5, 'Coletando dados para este período...', ha='center', va='center', fontsize=18, color='gray')
            ax.axis('off')
            buffer_imagem = io.BytesIO()
            fig.savefig(buffer_imagem, format='png')
            buffer_imagem.seek(0)
            plt.close(fig)
            return send_file(buffer_imagem, mimetype='image/png')

        agora = datetime.now()
        if periodo == 'diario':
            hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            df = df_completo[df_completo.index >= hoje_inicio].copy()
        elif periodo == 'semanal':
            inicio_periodo = agora - timedelta(days=7)
            df = df_completo[df_completo.index >= inicio_periodo].copy()
        elif periodo == 'mensal':
            inicio_periodo = agora - timedelta(days=30)
            df = df_completo[df_completo.index >= inicio_periodo].copy()
        else:
            df = df_completo.copy()

        if tanque_id == 1:
            coluna_tanque = 'SENSOR 1'
        elif tanque_id == 2:
            coluna_tanque = 'SENSOR 2'
        else:
            return "ID de tanque inválido.", 404
        
        df[coluna_tanque] = converter_para_percentual(df[coluna_tanque])

        fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
        
        for spine in ax.spines.values():
            spine.set_linewidth(1.5)

        ax.plot(df.index, df[coluna_tanque], marker='o', linestyle='-', markersize=4, color='blue', zorder=2)
        
        ax.set_ylim(0, 105)
        ax.set_ylabel('Percentual (%)', fontsize=12)
        ax.set_xlabel('Horário', fontsize=12)
        ax.grid(True)
        
        # --- MODIFICAÇÃO: Define os marcadores do eixo Y ---
        ticks_percentual = [0, 20, 40, 60, 80, 100]
        ax.set_yticks(ticks_percentual)
        
        ax_direita = ax.twinx()
        ax_direita.set_ylim(0, 105)
        # --- MODIFICAÇÃO: Define os mesmos marcadores para o eixo da direita ---
        ax_direita.set_yticks(ticks_percentual)
        
        date_format = mdates.DateFormatter('%H:%M')
        ax.xaxis.set_major_formatter(date_format)
        
        if periodo == 'diario':
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        
        plt.xticks(rotation=30, ha='right', fontsize=10)
        
        fig.tight_layout()
        
        buffer_imagem = io.BytesIO()
        fig.savefig(buffer_imagem, format='png')
        buffer_imagem.seek(0)
        plt.close(fig)
        
        return send_file(buffer_imagem, mimetype='image/png')
        
    except Exception as e:
        print(f"ERRO AO GERAR GRÁFICO DO RESERVATÓRIO {tanque_id}: {e}")
        traceback.print_exc()
        return Response(f"Erro ao gerar gráfico T{tanque_id}: {e}", status=500)
