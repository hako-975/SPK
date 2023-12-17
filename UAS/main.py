from http import HTTPStatus
from flask import Flask, request, abort
from flask_restful import Resource, Api 
from models import Ponsel as PonselModel
from engine import engine
from sqlalchemy import select
from sqlalchemy.orm import Session

session = Session(engine)

app = Flask(__name__)
api = Api(app)        

class BaseMethod():

    def __init__(self):
        self.raw_weight = {'harga': 4, 'kualitas_kamera': 3, 'kapasitas_baterai': 4, 'kinerja': 6, 'ukuran_layar': 3}

    @property
    def weight(self):
        total_weight = sum(self.raw_weight.values())
        return {k: round(v/total_weight, 2) for k, v in self.raw_weight.items()}

    @property
    def data(self):
        query = select(PonselModel.id_ponsel, PonselModel.harga, PonselModel.kualitas_kamera, PonselModel.kapasitas_baterai, PonselModel.kinerja, PonselModel.ukuran_layar)
        result = session.execute(query).fetchall()
        print(result)
        return [{'id_ponsel': ponsel.id_ponsel, 'harga': ponsel.harga, 'kualitas_kamera': ponsel.kualitas_kamera, 'kapasitas_baterai': ponsel.kapasitas_baterai, 'kinerja': ponsel.kinerja, 'ukuran_layar': ponsel.ukuran_layar} for ponsel in result]

    @property
    def normalized_data(self):
        harga_values = []
        kualitas_kamera_values = []
        kapasitas_baterai_values = []
        kinerja_values = []
        ukuran_layar_values = []

        for data in self.data:
            harga_values.append(data['harga'])
            kualitas_kamera_values.append(data['kualitas_kamera'])
            kapasitas_baterai_values.append(data['kapasitas_baterai'])
            kinerja_values.append(data['kinerja'])
            ukuran_layar_values.append(data['ukuran_layar'])

        return [
            {'id_ponsel': data['id_ponsel'],
             'harga': min(harga_values) / data['harga'],
             'kualitas_kamera': data['kualitas_kamera'] / max(kualitas_kamera_values),
             'kapasitas_baterai': data['kapasitas_baterai'] / max(kapasitas_baterai_values),
             'kinerja': data['kinerja'] / max(kinerja_values),
             'ukuran_layar': data['ukuran_layar'] / max(ukuran_layar_values)
             }
            for data in self.data
        ]

    def update_weights(self, new_weights):
        self.raw_weight = new_weights

class WeightedProductCalculator(BaseMethod):
    def update_weights(self, new_weights):
        self.raw_weight = new_weights

    @property
    def calculate(self):
        normalized_data = self.normalized_data
        produk = []

        for row in normalized_data:
            product_score = (
                row['harga'] ** self.raw_weight['harga'] *
                row['kualitas_kamera'] ** self.raw_weight['kualitas_kamera'] *
                row['kapasitas_baterai'] ** self.raw_weight['kapasitas_baterai'] *
                row['kinerja'] ** self.raw_weight['kinerja'] *
                row['ukuran_layar'] ** self.raw_weight['ukuran_layar']
            )

            produk.append({
                'id_ponsel': row['id_ponsel'],
                'produk': product_score
            })

        sorted_produk = sorted(produk, key=lambda x: x['produk'], reverse=True)

        sorted_data = []

        for product in sorted_produk:
            sorted_data.append({
                'id_ponsel': product['id_ponsel'],
                'score': product['produk']
            })

        return sorted_data


class WeightedProduct(Resource):
    def get(self):
        calculator = WeightedProductCalculator()
        result = calculator.calculate
        return result, HTTPStatus.OK.value
    
    def post(self):
        new_weights = request.get_json()
        calculator = WeightedProductCalculator()
        calculator.update_weights(new_weights)
        result = calculator.calculate
        return {'data': result}, HTTPStatus.OK.value
    

class SimpleAdditiveWeightingCalculator(BaseMethod):
    @property
    def calculate(self):
        weight = self.weight
        result = {row['id_ponsel']:
                  round(row['harga'] * weight['harga'] +
                        row['kualitas_kamera'] * weight['kualitas_kamera'] +
                        row['kapasitas_baterai'] * weight['kapasitas_baterai'] +
                        row['kinerja'] * weight['kinerja'] +
                        row['ukuran_layar'] * weight['ukuran_layar'], 2)
                  for row in self.normalized_data
                  }
        sorted_result = dict(
            sorted(result.items(), key=lambda x: x[1], reverse=True))
        return sorted_result

    def update_weights(self, new_weights):
        self.raw_weight = new_weights

class SimpleAdditiveWeighting(Resource):
    def get(self):
        saw = SimpleAdditiveWeightingCalculator()
        result = saw.calculate
        return result, HTTPStatus.OK.value

    def post(self):
        new_weights = request.get_json()
        saw = SimpleAdditiveWeightingCalculator()
        saw.update_weights(new_weights)
        result = saw.calculate
        return {'data': result}, HTTPStatus.OK.value


class Ponsel(Resource):
    def get_paginated_result(self, url, list, args):
        page_size = int(args.get('page_size', 10))
        page = int(args.get('page', 1))
        page_count = int((len(list) + page_size - 1) / page_size)
        start = (page - 1) * page_size
        end = min(start + page_size, len(list))

        if page < page_count:
            next_page = f'{url}?page={page+1}&page_size={page_size}'
        else:
            next_page = None
        if page > 1:
            prev_page = f'{url}?page={page-1}&page_size={page_size}'
        else:
            prev_page = None
        
        if page > page_count or page < 1:
            abort(404, description=f'Halaman {page} tidak ditemukan.') 
        return {
            'page': page, 
            'page_size': page_size,
            'next': next_page, 
            'prev': prev_page,
            'Results': list[start:end]
        }

    def get(self):
        query = select(PonselModel)
        data = [{'id_ponsel': ponsel.id_ponsel, 'harga': ponsel.harga, 'kualitas_kamera': ponsel.kualitas_kamera, 'kapasitas_baterai': ponsel.kapasitas_baterai, 'kinerja': ponsel.kinerja, 'ukuran_layar': ponsel.ukuran_layar} for ponsel in session.scalars(query)]
        return self.get_paginated_result('ponsel/', data, request.args), HTTPStatus.OK.value


api.add_resource(Ponsel, '/ponsel')
api.add_resource(WeightedProduct, '/wp')
api.add_resource(SimpleAdditiveWeighting, '/saw')

if __name__ == '__main__':
    app.run(port='5005', debug=True)
