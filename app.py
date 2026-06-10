from flask import Flask, render_template, request

application = Flask(__name__)

@application.route('/', methods=['GET', 'POST'])
def index():
   if request.method == 'POST':
      namaDepan = request.form['namaDepan']
      namaBelakang = request.form['namaBelakang']
      nama = '%s %s' % (namaDepan, namaBelakang)
      p = nama
      C = ' '
      k = 3
      for i in range(len(p)):
         c = chr(ord(p[i]) + k)
         C = C + c
      return render_template('response.html', nama=C)
   return render_template('form.html')

if __name__ == '__main__':
   application.run(debug=True)
